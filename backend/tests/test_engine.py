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
async def test_match_suppliers_only_checks_compliance_for_licensed_distributors(monkeypatch):
    # Regression: a previous version scored every distributor in the graph
    # against live openFDA enforcement, even ones with no chance of passing
    # (not licensed in the delivery state, no national coverage) -- at full
    # data-set scale (1,356 real distributors) that meant ~1,300 unnecessary
    # live HTTP calls per query. Add an unlicensed, non-national distributor
    # and assert it never reaches fetch_enforcement.
    graph = build_test_graph()
    graph.add_node(
        "dist:unlicensed",
        type="Distributor",
        name="Unlicensed Co",
        canonical_name="unlicensed_co",
        distributor_type="wholesale_distributor",
        home_state="WY",
        states_licensed=["WY"],
        national_coverage=False,
    )

    checked_names: list[str] = []

    async def tracking_fetch_enforcement(name):
        checked_names.append(name)
        return []

    monkeypatch.setattr(engine, "fetch_enforcement", tracking_fetch_enforcement)

    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    await engine.match_suppliers(graph, "drug:0363-0160", request)

    assert "Unlicensed Co" not in checked_names


@pytest.mark.asyncio
async def test_match_suppliers_uses_facility_geography_for_manufacturer_distance():
    graph = build_test_graph()
    mfr_id = next(n for n in graph.successors("drug:0363-0160") if graph.nodes[n]["type"] == "Manufacturer")
    graph.add_node("facility:test", type="Facility", state="CA")
    graph.add_edge(mfr_id, "facility:test", key="OPERATES")

    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)

    mfr_match = next(m for m in result.matches if m.supplier_type == "manufacturer_direct")
    assert mfr_match.distance_km is not None


@pytest.mark.asyncio
async def test_match_suppliers_returns_no_alternatives_when_matches_exist_and_no_shortage():
    graph = build_test_graph()
    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)
    assert result.alternatives == []


@pytest.mark.asyncio
async def test_match_suppliers_surfaces_alternatives_during_active_shortage(monkeypatch):
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
    graph.add_node("drug:te-alt", type="Drug", brand_name="Alt Drug", te_groups=["AB"], is_generic=True)
    graph.nodes["drug:0363-0160"]["te_groups"] = ["AB"]

    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)

    assert len(result.alternatives) == 1
    assert result.alternatives[0].drug_id == "drug:te-alt"
    assert result.alternatives[0].relationship == "therapeutic"


@pytest.mark.asyncio
async def test_match_suppliers_caps_returned_matches_but_reports_true_total():
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
            national_coverage=True,
        )
        graph.add_edge(node_id, "geo:IL", key="LICENSED_IN")

    request = ProcurementRequest(drug_name="acetaminophen", delivery_state="IL")
    result = await engine.match_suppliers(graph, "drug:0363-0160", request)

    assert result.matches_total > engine.MAX_RETURNED_MATCHES
    assert len(result.matches) == engine.MAX_RETURNED_MATCHES
    assert str(result.matches_total) in result.explanation


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
