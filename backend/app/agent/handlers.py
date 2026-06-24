from dataclasses import asdict

import networkx as nx

from app.graph.live_enrich import enrich_drug_with_shortage, enrich_manufacturer_with_compliance
from app.graph.queries import get_supply_chain, serialize_node
from app.matching.engine import match_suppliers as run_match_suppliers
from app.matching.models import ProcurementRequest
from app.matching.resolve import resolve_drug as run_resolve_drug


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
        return {"ambiguous": True, "disambiguation_options": resolution.disambiguation_options}
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
            "note": "Facility-level compliance data unavailable -- DECRS not yet ingested (see data/MANUAL_DOWNLOADS.md).",
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
    drug_id = kwargs["drug_id"]
    if not graph.has_node(drug_id):
        return {"error": f"Drug {drug_id!r} not found."}
    drug = graph.nodes[drug_id]
    substances = set(drug.get("substance_name", []))
    alternatives = []
    if substances:
        for other_id, other in graph.nodes(data=True):
            if other_id == drug_id or other.get("type") != "Drug" or other.get("status") != "active":
                continue
            if set(other.get("substance_name", [])) == substances:
                alternatives.append(
                    {
                        "drug_id": other_id,
                        "generic_name": other.get("generic_name"),
                        "brand_name": other.get("brand_name"),
                        "relationship": "shared_ingredient",
                    }
                )
    return {
        "drug_id": drug_id,
        "alternatives": alternatives[:10],
        "caveat": "Orange Book therapeutic/generic equivalence data is not yet ingested (see data/MANUAL_DOWNLOADS.md) -- these are same-active-ingredient matches only, not confirmed substitutes.",
    }


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
        "alternatives": [asdict(a) for a in result.alternatives],
        "risk_summary": asdict(result.risk_summary) if result.risk_summary else None,
        "explanation": result.explanation,
    }


async def handle_get_distributor_coverage(graph: nx.MultiDiGraph, **kwargs) -> dict:
    state = kwargs["state"].upper()
    distributors = [
        _node_summary(graph, n)
        for n, d in graph.nodes(data=True)
        if d.get("type") == "Distributor" and graph.has_edge(n, f"geo:{state}", key="LICENSED_IN")
    ]
    return {"state": state, "distributors": distributors}


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
