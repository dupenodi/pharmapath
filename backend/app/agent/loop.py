import networkx as nx

from app.agent.anthropic_loop import run_anthropic_turn
from app.agent.gemini_loop import run_gemini_turn
from app.core.config import settings


async def run_agent_turn(graph: nx.MultiDiGraph, session_id: str, message: str) -> dict:
    """Dispatches to whichever LLM provider is configured (settings.agent_provider).

    Both providers share the same 8 tools, system prompt, and
    render_component contract -- only the model driving the loop differs.
    """
    if settings.agent_provider == "gemini":
        return await run_gemini_turn(graph, session_id, message)
    return await run_anthropic_turn(graph, session_id, message)
