from datetime import date

import pytest

from app.graph import live_enrich
from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import parse_ndc_records
from app.services.openfda_models import ComplianceFlag, Shortage
from tests.test_ndc_ingestion import load_fixture


def build_test_graph():
    return build_graph(
        ndc_records=parse_ndc_records(load_fixture()),
        distributor_records=load_big3_distributors(),
        geography_records=load_geography_records(),
    )


@pytest.mark.asyncio
async def test_enrich_drug_with_label_adds_active_ingredient_nodes(monkeypatch):
    graph = build_test_graph()

    async def fake_fetch_label(generic_name):
        return {"inactive_ingredient": ["Inactive ingredients: starch, talc"]}

    monkeypatch.setattr(live_enrich, "fetch_label", fake_fetch_label)

    await live_enrich.enrich_drug_with_label(graph, "drug:0363-0160")

    ing_id = "ingredient:acetaminophen"
    assert graph.has_node(ing_id)
    assert graph.has_edge("drug:0363-0160", ing_id)
    edge_data = graph.get_edge_data("drug:0363-0160", ing_id, key="CONTAINS")
    assert edge_data["is_active"] is True
    assert graph.has_node("ingredient:starch")


@pytest.mark.asyncio
async def test_enrich_manufacturer_with_compliance_upserts_flag(monkeypatch):
    graph = build_test_graph()

    async def fake_fetch_enforcement(firm_name):
        return [
            ComplianceFlag(
                id="D-1234-2026",
                flag_type="recall",
                severity="critical",
                status="active",
                issued_date="20260101",
                closed_date=None,
                description="test recall",
                source_url=None,
                affected_products=["test product"],
            )
        ]

    monkeypatch.setattr(live_enrich, "fetch_enforcement", fake_fetch_enforcement)

    flags = await live_enrich.enrich_manufacturer_with_compliance(graph, "mfr:walgreens")

    assert len(flags) == 1
    assert graph.has_node("flag:D-1234-2026")
    assert graph.has_edge("mfr:walgreens", "flag:D-1234-2026", key="HAS_FLAG")


@pytest.mark.asyncio
async def test_enrich_drug_with_shortage_upserts_shortage(monkeypatch):
    graph = build_test_graph()

    async def fake_fetch_shortages(generic_name):
        return [
            Shortage(
                id="shortage-1",
                drug_name="Acetaminophen 500mg",
                generic_name="Acetaminophen",
                status="active",
                reason="manufacturing delay",
                start_date="20260101",
                resolved_date=None,
                affected_firms=["Walgreens"],
                last_checked=date.today(),
            )
        ]

    monkeypatch.setattr(live_enrich, "fetch_shortages", fake_fetch_shortages)

    shortages = await live_enrich.enrich_drug_with_shortage(graph, "drug:0363-0160")

    assert len(shortages) == 1
    assert graph.has_node("shortage:shortage-1")
    assert graph.has_edge("drug:0363-0160", "shortage:shortage-1", key="HAS_SHORTAGE")
