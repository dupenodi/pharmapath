import networkx as nx

from app.ingestion.label import parse_inactive_ingredients
from app.ingestion.name_normalize import normalize_name
from app.services.openfda import fetch_enforcement, fetch_label, fetch_shortages
from app.services.openfda_models import ComplianceFlag, Shortage


def _active_ingredient_id(name: str) -> str:
    return f"ingredient:{normalize_name(name).replace(' ', '_')}"


async def enrich_drug_with_label(graph: nx.MultiDiGraph, drug_id: str) -> None:
    """Pipeline step 2 (lazy): adds ActiveIngredient + excipient nodes for one Drug.

    Active ingredients come from the Drug node's own substance_name (already
    structured from NDC). Excipients come from the live label lookup.
    """
    if not graph.has_node(drug_id):
        return
    drug = graph.nodes[drug_id]

    for name in drug.get("substance_name", []):
        ing_id = _active_ingredient_id(name)
        if not graph.has_node(ing_id):
            graph.add_node(ing_id, type="ActiveIngredient", name=name.title(), synonyms=[])
        if not graph.has_edge(drug_id, ing_id):
            graph.add_edge(drug_id, ing_id, key="CONTAINS", is_active=True)

    label = await fetch_label(drug.get("generic_name", ""))
    if label is None:
        return
    for name in parse_inactive_ingredients(label):
        ing_id = _active_ingredient_id(name)
        if not graph.has_node(ing_id):
            graph.add_node(ing_id, type="ActiveIngredient", name=name, synonyms=[])
        if not graph.has_edge(drug_id, ing_id):
            graph.add_edge(drug_id, ing_id, key="CONTAINS", is_active=False)


def _upsert_compliance_flags(graph: nx.MultiDiGraph, entity_id: str, flags: list[ComplianceFlag]) -> None:
    for flag in flags:
        flag_id = f"flag:{flag.id}"
        if not graph.has_node(flag_id):
            graph.add_node(flag_id, type="ComplianceFlag", **flag.model_dump())
        if not graph.has_edge(entity_id, flag_id, key="HAS_FLAG"):
            graph.add_edge(entity_id, flag_id, key="HAS_FLAG", active=flag.status == "active")


async def enrich_manufacturer_with_compliance(graph: nx.MultiDiGraph, manufacturer_id: str) -> list[ComplianceFlag]:
    """Pipeline step 6 (lazy, per query): live openFDA recall lookup for one manufacturer."""
    if not graph.has_node(manufacturer_id):
        return []
    raw_names = graph.nodes[manufacturer_id].get("raw_names", [])
    if not raw_names:
        return []
    flags = await fetch_enforcement(raw_names[0])
    _upsert_compliance_flags(graph, manufacturer_id, flags)
    return flags


def _upsert_shortage(graph: nx.MultiDiGraph, drug_id: str, shortages: list[Shortage]) -> None:
    for shortage in shortages:
        shortage_id = f"shortage:{shortage.id}"
        if not graph.has_node(shortage_id):
            graph.add_node(shortage_id, type="Shortage", **shortage.model_dump(mode="json"))
        if not graph.has_edge(drug_id, shortage_id, key="HAS_SHORTAGE"):
            graph.add_edge(drug_id, shortage_id, key="HAS_SHORTAGE", active=shortage.status == "active")


async def enrich_drug_with_shortage(graph: nx.MultiDiGraph, drug_id: str) -> list[Shortage]:
    """Pipeline step 6 (lazy, per query): live openFDA shortage lookup for one drug."""
    if not graph.has_node(drug_id):
        return []
    generic_name = graph.nodes[drug_id].get("generic_name", "")
    if not generic_name:
        return []
    shortages = await fetch_shortages(generic_name)
    _upsert_shortage(graph, drug_id, shortages)
    return shortages
