import json

import networkx as nx
from anthropic import AsyncAnthropic

from app.agent.sessions import get_history
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tool_runner import MAX_TOOL_ITERATIONS, run_tool
from app.agent.tools import TOOLS
from app.core.config import settings


async def run_anthropic_turn(graph: nx.MultiDiGraph, session_id: str, message: str) -> dict:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    history = get_history(session_id)
    history.append({"role": "user", "content": message})

    tool_calls_log: list[dict] = []
    component: str | None = None
    component_data: dict | None = None
    warnings: list[str] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )
        assistant_content = [block.model_dump() for block in response.content]
        history.append({"role": "assistant", "content": assistant_content})

        tool_use_blocks = [b for b in assistant_content if b["type"] == "tool_use"]
        if not tool_use_blocks:
            text = "".join(b["text"] for b in assistant_content if b["type"] == "text")
            break

        tool_results = []
        for block in tool_use_blocks:
            result = await run_tool(graph, block["name"], block["input"])
            tool_calls_log.append({"name": block["name"], "input": block["input"], "result": result})
            if block["name"] == "render_component":
                component = result.get("component")
                component_data = result.get("data")
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(result, default=str)}
            )
        history.append({"role": "user", "content": tool_results})
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
