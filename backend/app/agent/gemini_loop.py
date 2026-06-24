import networkx as nx
from google import genai
from google.genai import types

from app.agent.sessions import get_history
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tool_runner import MAX_TOOL_ITERATIONS, run_tool
from app.agent.tools import TOOLS
from app.core.config import settings


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
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=history,
            config=config,
        )
        candidate_content = response.candidates[0].content
        history.append(candidate_content)

        function_calls = [p.function_call for p in candidate_content.parts if p.function_call]
        if not function_calls:
            text = response.text or ""
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
