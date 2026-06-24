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
    assert "DECRS not yet ingested" in result["note"]


@pytest.mark.asyncio
async def test_check_shortage_handler_returns_empty_when_no_shortage():
    graph = build_test_graph()
    result = await handlers.handle_check_shortage(graph, drug_id="drug:71335-9603")
    assert result["shortages"] == []


@pytest.mark.asyncio
async def test_find_alternatives_handler_includes_orange_book_caveat():
    graph = build_test_graph()
    result = await handlers.handle_find_alternatives(graph, drug_id="drug:71335-9603")
    assert "Orange Book" in result["caveat"]


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
    assert len(result["distributors"]) == 3


@pytest.mark.asyncio
async def test_render_component_handler_passes_through():
    graph = build_test_graph()
    result = await handlers.handle_render_component(graph, component="supplier_table", data={"rows": []})
    assert result == {"component": "supplier_table", "data": {"rows": []}}
