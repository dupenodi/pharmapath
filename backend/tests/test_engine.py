from datetime import date

import pytest

from app.graph import live_enrich
from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import parse_ndc_records
from app.matching import engine
from app.matching.models import ProcurementRequest
from app.services.openfda_models import Shortage
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

    monkeypatch.setattr(engine, "fetch_enforcement", no_flags)
    monkeypatch.setattr(live_enrich, "fetch_enforcement", no_flags)
    monkeypatch.setattr(live_enrich, "fetch_shortages", no_shortages)


@pytest.mark.asyncio
async def test_match_suppliers_requires_delivery_state():
    graph = build_test_graph()
    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)
    assert result.matches == []
    assert "delivery state" in result.explanation.lower()


@pytest.mark.asyncio
async def test_match_suppliers_returns_big3_distributors_for_any_state():
    graph = build_test_graph()
    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)
    distributor_names = {m.supplier_name for m in result.matches if m.supplier_type == "distributor"}
    assert "McKesson Corporation" in distributor_names
    assert "Cardinal Health, Inc." in distributor_names
    assert "Cencora, Inc. (formerly AmerisourceBergen)" in distributor_names


@pytest.mark.asyncio
async def test_match_suppliers_sorted_by_score_descending():
    graph = build_test_graph()
    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)
    scores = [m.score for m in result.matches]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_large_quantity_filters_to_national_coverage_only(monkeypatch):
    graph = build_test_graph()
    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL", quantity=60_000)
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)
    assert all(m.supplier_type != "distributor" or "national" in " ".join(m.caveats).lower() for m in result.matches)


@pytest.mark.asyncio
async def test_active_shortage_drives_risk_summary(monkeypatch):
    async def shortage_for_drug(generic_name):
        return [
            Shortage(
                id="s1",
                drug_name="Acetaminophen",
                generic_name="Acetaminophen",
                status="active",
                reason="manufacturing delay",
                start_date="20260101",
                resolved_date=None,
                affected_firms=[],
                last_checked=date.today(),
            )
        ]

    monkeypatch.setattr(live_enrich, "fetch_shortages", shortage_for_drug)

    graph = build_test_graph()
    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)
    assert result.risk_summary.shortage_active is True
    assert any("manufacturing delay" in flag for flag in result.risk_summary.risk_flags)
