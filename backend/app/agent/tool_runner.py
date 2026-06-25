import networkx as nx

from app.agent.handlers import HANDLERS

MAX_TOOL_ITERATIONS = 8


async def run_tool(graph: nx.MultiDiGraph, name: str, tool_input: dict) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool {name!r}"}
    return await handler(graph, **tool_input)


def fallback_render_component(tool_calls_log: list[dict], message: str) -> tuple[str, dict] | None:
    """Some models occasionally describe disambiguation options in prose
    without actually calling render_component (seen live with gpt-4o), so the
    frontend never gets a clickable disambiguation_prompt. The data needed is
    fully deterministic -- it's exactly what resolve_drug already returned --
    so synthesize the component here rather than relying on every model to
    remember this every time."""
    for entry in reversed(tool_calls_log):
        if entry["name"] == "resolve_drug" and entry["result"].get("ambiguous"):
            options = entry["result"].get("disambiguation_options") or []
            if options:
                return "disambiguation_prompt", {"query": message, "options": options}
            return None
    return None
