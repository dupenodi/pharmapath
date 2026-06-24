import networkx as nx

from app.agent.handlers import HANDLERS

MAX_TOOL_ITERATIONS = 8


async def run_tool(graph: nx.MultiDiGraph, name: str, tool_input: dict) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool {name!r}"}
    return await handler(graph, **tool_input)
