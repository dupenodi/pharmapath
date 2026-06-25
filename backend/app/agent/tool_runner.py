import networkx as nx

from app.agent.handlers import HANDLERS

MAX_TOOL_ITERATIONS = 8


async def run_tool(graph: nx.MultiDiGraph, name: str, tool_input: dict) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool {name!r}"}
    return await handler(graph, **tool_input)


def _find_drug_name(tool_calls_log: list[dict]) -> str | None:
    for entry in tool_calls_log:
        if entry["name"] == "resolve_drug":
            drugs = entry["result"].get("drugs") or []
            if drugs:
                return drugs[0].get("generic_name") or drugs[0].get("brand_name")
    return None


def _shortage_risk_summary(shortages: list[dict]) -> dict:
    active = [s for s in shortages if s.get("status") == "active"]
    return {
        "overall_risk": "high" if active else "low",
        "shortage_active": bool(active),
        "manufacturers_flagged": 0,
        "manufacturers_total": 0,
        "risk_flags": [s["reason"] for s in shortages if s.get("reason")],
    }


def fallback_render_component(tool_calls_log: list[dict], message: str) -> tuple[str, dict] | None:
    """Models occasionally produce a correct final answer in prose without
    actually calling render_component (seen live with gpt-4o, on both a
    disambiguation case and a supplier-match case), so the frontend never gets
    a UI component to show. The data needed in every one of these cases is
    fully deterministic -- it's exactly what the underlying tool already
    returned -- so synthesize the component here rather than relying on every
    model to remember this instruction every time. Walks tool_calls_log in
    reverse so the most recent/most-specific deliverable wins (e.g. if both
    check_shortage and match_suppliers ran, match_suppliers' supplier_table
    is the more useful answer to a procurement request)."""
    for entry in reversed(tool_calls_log):
        name, result = entry["name"], entry["result"]
        if name == "resolve_drug" and result.get("ambiguous"):
            options = result.get("disambiguation_options") or []
            if options:
                return "disambiguation_prompt", {"query": message, "options": options}
        elif name == "match_suppliers" and result.get("matches") is not None:
            return "supplier_table", {"matches": result["matches"], "explanation": result.get("explanation")}
        elif name == "check_shortage" and result.get("shortages") is not None:
            return "risk_card", {
                "drug_name": _find_drug_name(tool_calls_log) or result.get("drug_id"),
                "risk_summary": _shortage_risk_summary(result["shortages"]),
                "shortages": result["shortages"],
            }
        elif name == "get_supply_chain" and result.get("nodes") is not None:
            return "supply_chain_graph", result
        elif name == "get_distributor_coverage" and result.get("distributors") is not None:
            return "map_view", result
    return None
