import asyncio

import networkx as nx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.agent.sessions import get_history
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tool_runner import MAX_TOOL_ITERATIONS, run_tool
from app.agent.tools import TOOLS
from app.core.config import settings

GENERATE_RETRY_DELAYS_SECONDS = (2, 5, 10)
RATE_LIMIT_RETRY_DELAY_SECONDS = 15.0
RATE_LIMIT_MAX_RETRIES = 3


def _build_tool() -> types.Tool:
    declarations = [
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters_json_schema=t["input_schema"],
        )
        for t in TOOLS
    ]
    return types.Tool(function_declarations=declarations)


def _is_rate_limited(error: genai_errors.ClientError) -> bool:
    return getattr(error, "code", None) == 429


async def _generate_with_retry(client: genai.Client, **kwargs):
    """Gemini's hosted models occasionally return 503 UNAVAILABLE under load
    (transient) and free-tier keys can hit 429 RESOURCE_EXHAUSTED (rate limit,
    e.g. 5 requests/minute for gemini-2.5-flash) -- neither is a code bug.
    Retry both with backoff before giving up."""
    last_error: genai_errors.APIError | None = None
    rate_limit_retries = 0
    for delay in (0, *GENERATE_RETRY_DELAYS_SECONDS):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await client.aio.models.generate_content(**kwargs)
        except genai_errors.ServerError as e:
            last_error = e
        except genai_errors.ClientError as e:
            if not _is_rate_limited(e) or rate_limit_retries >= RATE_LIMIT_MAX_RETRIES:
                raise
            rate_limit_retries += 1
            last_error = e
            await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
    raise last_error


async def run_gemini_turn(graph: nx.MultiDiGraph, session_id: str, message: str) -> dict:
    client = genai.Client(api_key=settings.gemini_api_key)
    history = get_history(session_id)
    history.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    tool_calls_log: list[dict] = []
    component: str | None = None
    component_data: dict | None = None
    warnings: list[str] = []
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=[_build_tool()])

    text = ""
    for _ in range(MAX_TOOL_ITERATIONS):
        response = await _generate_with_retry(
            client,
            model=settings.gemini_model,
            contents=history,
            config=config,
        )
        candidate = response.candidates[0]
        candidate_content = candidate.content
        parts = (candidate_content.parts if candidate_content else None) or []
        if candidate_content is not None:
            history.append(candidate_content)

        function_calls = [p.function_call for p in parts if p.function_call]
        if not function_calls:
            text = response.text or ""
            if not text:
                # candidate_content.parts came back None/empty with no text either
                # -- e.g. a safety block or an unusual finish_reason. Surface that
                # instead of silently returning an empty answer.
                finish_reason = getattr(candidate, "finish_reason", None)
                text = f"The model returned an empty response (finish_reason={finish_reason})."
                warnings.append(text)
            break

        response_parts = []
        for fc in function_calls:
            tool_input = dict(fc.args or {})
            result = await run_tool(graph, fc.name, tool_input)
            tool_calls_log.append({"name": fc.name, "input": tool_input, "result": result})
            if fc.name == "render_component":
                component = result.get("component")
                component_data = result.get("data")
            response_parts.append(types.Part.from_function_response(name=fc.name, response=result))
        history.append(types.Content(role="tool", parts=response_parts))
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
