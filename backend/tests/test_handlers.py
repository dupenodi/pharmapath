import pytest

from app.agent import handlers
from app.graph import live_enrich
from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import parse_ndc_records
from app.matching import engine
from tests.test_ndc_ingestion import load_fixture


def build_test_graph():
    return build_graph(
        ndc_records=parse_ndc_records(load_fixture()),
        distributor_records=load_big3_distributors(),
        geography_records=load_geography_records(),
    )


@pytest.fixture(autouse=True)
def stub_openfda(monkeypatch):
    async def no_flags(name):
        return []

    async def no_shortages(name):
        return []

    async def no_label(name):
        return None

    monkeypatch.setattr(live_enrich, "fetch_enforcement", no_flags)
    monkeypatch.setattr(live_enrich, "fetch_shortages", no_shortages)
    monkeypatch.setattr(live_enrich, "fetch_label", no_label)
    monkeypatch.setattr(engine, "fetch_enforcement", no_flags)


@pytest.mark.asyncio
async def test_resolve_drug_handler_returns_drug_ids():
    graph = build_test_graph()
    result = await handlers.handle_resolve_drug(graph, drug_name="Butalbital, Acetaminophen and Caffeine")
    assert result["drug_ids"] == ["drug:71335-9603"]


@pytest.mark.asyncio
async def test_get_supply_chain_handler_includes_manufacturer():
    graph = build_test_graph()
    result = await handlers.handle_get_supply_chain(graph, drug_id="drug:71335-9603", include_compliance=True)
    types = {n["type"] for n in result["nodes"]}
    assert "Manufacturer" in types


@pytest.mark.asyncio
async def test_get_compliance_status_handler_facility_says_unavailable():
    graph = build_test_graph()
    result = await handlers.handle_get_compliance_status(graph, entity_id="facility:x", entity_type="facility")
    assert result["status"] == "unknown"
    assert "manufacturer" in result["note"].lower()


@pytest.mark.asyncio
async def test_check_shortage_handler_returns_empty_when_no_shortage():
    graph = build_test_graph()
    result = await handlers.handle_check_shortage(graph, drug_id="drug:71335-9603")
    assert result["shortages"] == []


@pytest.mark.asyncio
async def test_find_alternatives_handler_notes_when_none_found():
    # The fixture graph has no Orange Book index loaded, so no drug has a
    # te_groups match -- the handler should say so rather than silently
    # returning an empty list with no explanation.
    graph = build_test_graph()
    result = await handlers.handle_find_alternatives(graph, drug_id="drug:71335-9603")
    assert result["alternatives"] == []
    assert result["total"] == 0
    assert "note" in result


@pytest.mark.asyncio
async def test_find_alternatives_handler_returns_real_te_matches():
    graph = build_test_graph()
    # Two synthetic drugs sharing a TE group, the same shape build.py produces
    # from a real Orange Book index -- exercises the canonical TE-based path
    # without needing to fabricate a full Orange Book ingestion fixture.
    graph.add_node("drug:te-a", type="Drug", brand_name="Test Drug A", te_groups=["AB"], is_generic=True)
    graph.add_node("drug:te-b", type="Drug", brand_name="Test Drug B", te_groups=["AB"], is_generic=True)
    result = await handlers.handle_find_alternatives(graph, drug_id="drug:te-a")
    assert result["total"] == 1
    assert result["alternatives"][0]["drug_id"] == "drug:te-b"
    assert result["alternatives"][0]["relationship"] == "therapeutic_equivalent"
    assert "note" not in result


@pytest.mark.asyncio
async def test_match_suppliers_handler_returns_distributors():
    graph = build_test_graph()
    result = await handlers.handle_match_suppliers(graph, drug_id="drug:71335-9603", delivery_state="IL")
    assert len(result["matches"]) > 0


@pytest.mark.asyncio
async def test_get_distributor_coverage_handler_returns_big3():
    graph = build_test_graph()
    result = await handlers.handle_get_distributor_coverage(graph, state="il")
    assert result["state"] == "IL"
    assert result["total"] == 3
    assert len(result["distributors"]) == 3
    assert "note" not in result


@pytest.mark.asyncio
async def test_get_distributor_coverage_handler_caps_large_results():
    graph = build_test_graph()
    for i in range(30):
        node_id = f"dist:synthetic-{i}"
        graph.add_node(
            node_id,
            type="Distributor",
            name=f"Synthetic Distributor {i}",
            canonical_name=f"synthetic_{i}",
            distributor_type="wholesale_distributor",
            home_state="IL",
            states_licensed=["IL"],
            national_coverage=False,
        )
        graph.add_edge(node_id, "geo:IL", key="LICENSED_IN")

    result = await handlers.handle_get_distributor_coverage(graph, state="il")
    assert result["total"] == 33  # 30 synthetic + the 3 big-3 fixture distributors
    assert len(result["distributors"]) == handlers.DISTRIBUTOR_COVERAGE_DEFAULT_LIMIT
    assert "note" in result

    result_with_limit = await handlers.handle_get_distributor_coverage(graph, state="il", limit=5)
    assert len(result_with_limit["distributors"]) == 5


@pytest.mark.asyncio
async def test_render_component_handler_passes_through():
    graph = build_test_graph()
    result = await handlers.handle_render_component(graph, component="supplier_table", data={"rows": []})
    assert result == {"component": "supplier_table", "data": {"rows": []}}
