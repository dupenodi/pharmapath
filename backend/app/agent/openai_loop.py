import asyncio
import json

import networkx as nx
import openai

from app.agent.sessions import get_history
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tool_runner import MAX_TOOL_ITERATIONS, run_tool
from app.agent.tools import TOOLS
from app.core.config import settings

GENERATE_RETRY_DELAYS_SECONDS = (2, 5, 10)
RATE_LIMIT_RETRY_DELAY_SECONDS = 15.0
RATE_LIMIT_MAX_RETRIES = 3


def _build_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


async def _create_with_retry(client: openai.AsyncOpenAI, **kwargs):
    """OpenAI's API can return transient 5xx errors and 429 rate limits --
    neither is a code bug. Retry both with backoff before giving up."""
    last_error: Exception | None = None
    rate_limit_retries = 0
    for delay in (0, *GENERATE_RETRY_DELAYS_SECONDS):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            if rate_limit_retries >= RATE_LIMIT_MAX_RETRIES:
                raise
            rate_limit_retries += 1
            last_error = e
            await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
        except (openai.APIStatusError, openai.APIConnectionError) as e:
            last_error = e
    raise last_error


async def run_openai_turn(graph: nx.MultiDiGraph, session_id: str, message: str) -> dict:
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    history = get_history(session_id)
    history.append({"role": "user", "content": message})

    tool_calls_log: list[dict] = []
    component: str | None = None
    component_data: dict | None = None
    warnings: list[str] = []
    tools = _build_tools()

    text = ""
    for _ in range(MAX_TOOL_ITERATIONS):
        response = await _create_with_retry(
            client,
            model=settings.openai_model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history],
            tools=tools,
        )
        message_obj = response.choices[0].message
        history.append(message_obj.model_dump(exclude_none=True))

        tool_calls = message_obj.tool_calls or []
        if not tool_calls:
            text = message_obj.content or ""
            break

        for tc in tool_calls:
            tool_input = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = await run_tool(graph, tc.function.name, tool_input)
            tool_calls_log.append({"name": tc.function.name, "input": tool_input, "result": result})
            if tc.function.name == "render_component":
                component = result.get("component")
                component_data = result.get("data")
            history.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
    else:
        text = "I wasn't able to finish processing this request within the available tool-call budget."
        warnings.append("Agent loop reached MAX_TOOL_ITERATIONS without a final response.")

    if component is None:
        warnings.append("Agent did not call render_component -- no UI component selected for this response.")

    return {
        "agent_response": text,
        "component": component,
        "component_data": component_data,
        "tool_calls": tool_calls_log,
        "warnings": warnings,
    }
