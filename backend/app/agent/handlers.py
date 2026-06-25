from dataclasses import asdict

import networkx as nx

from app.graph.live_enrich import enrich_drug_with_shortage, enrich_manufacturer_with_compliance
from app.graph.queries import find_alternatives as find_te_alternatives
from app.graph.queries import get_supply_chain, serialize_node
from app.matching.engine import match_suppliers as run_match_suppliers
from app.matching.models import ProcurementRequest
from app.matching.resolve import resolve_drug as run_resolve_drug

DISTRIBUTOR_COVERAGE_DEFAULT_LIMIT = 20


def _node_summary(graph: nx.MultiDiGraph, node_id: str) -> dict:
    node = serialize_node(graph, node_id)
    return node or {"id": node_id, "error": "not found"}


async def handle_resolve_drug(graph: nx.MultiDiGraph, **kwargs) -> dict:
    resolution = run_resolve_drug(
        graph,
        drug_name=kwargs["drug_name"],
        dosage_form=kwargs.get("dosage_form"),
        strength=kwargs.get("strength"),
        prefer_generic=kwargs.get("prefer_generic", False),
    )
    if resolution.ambiguous:
        response = {
            "ambiguous": True,
            "disambiguation_options": resolution.disambiguation_options,
            "disambiguation_total": resolution.disambiguation_total,
        }
        if resolution.disambiguation_total > len(resolution.disambiguation_options):
            response["note"] = (
                f"Showing {len(resolution.disambiguation_options)} of {resolution.disambiguation_total} "
                "possible matches -- ask the user to narrow it down (dosage, strength, or brand vs generic) "
                "rather than guessing among this many."
            )
        return response
    if not resolution.drug_ids:
        return {"ambiguous": False, "drug_ids": [], "note": "No matching drug found in the graph."}
    return {
        "ambiguous": False,
        "drug_ids": resolution.drug_ids,
        "drugs": [_node_summary(graph, d) for d in resolution.drug_ids[:5]],
    }


async def handle_get_supply_chain(graph: nx.MultiDiGraph, **kwargs) -> dict:
    drug_id = kwargs["drug_id"]
    subgraph = get_supply_chain(graph, drug_id)
    if subgraph is None:
        return {"error": f"Drug {drug_id!r} not found."}
    if kwargs.get("include_compliance", True):
        for node in subgraph["nodes"]:
            if node.get("type") == "Manufacturer":
                flags = await enrich_manufacturer_with_compliance(graph, node["id"])
                node["active_flags"] = [f.model_dump() for f in flags]
    return subgraph


async def handle_get_compliance_status(graph: nx.MultiDiGraph, **kwargs) -> dict:
    entity_id, entity_type = kwargs["entity_id"], kwargs["entity_type"]
    if entity_type == "facility":
        return {
            "entity_id": entity_id,
            "status": "unknown",
            "note": (
                "openFDA enforcement data only resolves to a firm/manufacturer name, not a "
                "specific facility -- check the operating manufacturer's compliance status instead."
            ),
        }
    if not graph.has_node(entity_id):
        return {"entity_id": entity_id, "status": "unknown", "note": "Manufacturer not found in graph."}
    flags = await enrich_manufacturer_with_compliance(graph, entity_id)
    status = "clean" if not any(f.status == "active" for f in flags) else "flagged"
    return {"entity_id": entity_id, "status": status, "active_flags": [f.model_dump() for f in flags]}


async def handle_check_shortage(graph: nx.MultiDiGraph, **kwargs) -> dict:
    drug_id = kwargs["drug_id"]
    if not graph.has_node(drug_id):
        return {"error": f"Drug {drug_id!r} not found."}
    shortages = await enrich_drug_with_shortage(graph, drug_id)
    return {"drug_id": drug_id, "shortages": [s.model_dump(mode="json") for s in shortages]}


async def handle_find_alternatives(graph: nx.MultiDiGraph, **kwargs) -> dict:
    """Therapeutic equivalents from the real Orange Book TE-code data.

    Drugs sharing a TE group (e.g. AB-rated) are confirmed interchangeable --
    a materially stronger claim than "shares an active ingredient", which is
    why this defers to queries.find_alternatives rather than re-deriving a
    weaker same-substance heuristic here.
    """
    drug_id = kwargs["drug_id"]
    if not graph.has_node(drug_id):
        return {"error": f"Drug {drug_id!r} not found."}
    result = find_te_alternatives(graph, drug_id, cap=kwargs.get("cap", 24))
    alternatives = [
        {
            "drug_id": item["id"],
            "label": item["label"],
            "is_generic": item["is_generic"],
            "relationship": "therapeutic_equivalent",
        }
        for item in result["items"]
    ]
    response = {"drug_id": drug_id, "alternatives": alternatives, "total": result["total"]}
    if not result["total"]:
        response["note"] = "No Orange Book therapeutic equivalents found for this drug."
    return response


async def handle_match_suppliers(graph: nx.MultiDiGraph, **kwargs) -> dict:
    drug_id = kwargs["drug_id"]
    request = ProcurementRequest(
        drug_name="",
        delivery_state=kwargs.get("delivery_state", ""),
        quantity=kwargs.get("quantity"),
        deadline_days=kwargs.get("deadline_days"),
        prefer_generic=kwargs.get("prefer_generic", False),
    )
    result = await run_match_suppliers(graph, drug_id, request)
    return {
        "resolved_drug_id": result.resolved_drug_id,
        "matches": [asdict(m) for m in result.matches],
        "matches_total": result.matches_total,
        "alternatives": [asdict(a) for a in result.alternatives],
        "risk_summary": asdict(result.risk_summary) if result.risk_summary else None,
        "explanation": result.explanation,
    }


async def handle_get_distributor_coverage(graph: nx.MultiDiGraph, **kwargs) -> dict:
    """Licensed distributors for a state, capped so a populous state (e.g. CA
    has ~500) doesn't dump hundreds of entries into the model's context.
    Sorted national-coverage-first, since those are the most generally useful
    candidates to mention first when the list is truncated.
    """
    state = kwargs["state"].upper()
    limit = kwargs.get("limit", DISTRIBUTOR_COVERAGE_DEFAULT_LIMIT)
    matches = [
        (n, d)
        for n, d in graph.nodes(data=True)
        if d.get("type") == "Distributor" and graph.has_edge(n, f"geo:{state}", key="LICENSED_IN")
    ]
    matches.sort(key=lambda nd: (not nd[1].get("national_coverage"), nd[1].get("name", "")))
    page = matches[:limit]
    response = {
        "state": state,
        "total": len(matches),
        "distributors": [_node_summary(graph, n) for n, _ in page],
    }
    if len(matches) > limit:
        response["note"] = f"Showing {limit} of {len(matches)} licensed distributors; ask for more if needed."
    return response


async def handle_render_component(graph: nx.MultiDiGraph, **kwargs) -> dict:
    return {"component": kwargs["component"], "data": kwargs["data"]}


HANDLERS = {
    "resolve_drug": handle_resolve_drug,
    "get_supply_chain": handle_get_supply_chain,
    "get_compliance_status": handle_get_compliance_status,
    "check_shortage": handle_check_shortage,
    "find_alternatives": handle_find_alternatives,
    "match_suppliers": handle_match_suppliers,
    "get_distributor_coverage": handle_get_distributor_coverage,
    "render_component": handle_render_component,
}
