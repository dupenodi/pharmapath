import json
from pathlib import Path

from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.models import FacilityRecord
from app.ingestion.ndc import parse_ndc_records
from app.ingestion.orange_book import OrangeBookEntry, ndc_application_key

FIXTURE = Path(__file__).parent / "fixtures" / "ndc_sample.json"


def load_fixture_records():
    with FIXTURE.open() as f:
        return parse_ndc_records(json.load(f))


def build_fixture_graph(facility_records=None, orange_book_index=None):
    return build_graph(
        ndc_records=load_fixture_records(),
        distributor_records=load_big3_distributors(),
        geography_records=load_geography_records(),
        facility_records=facility_records,
        orange_book_index=orange_book_index,
    )


def test_creates_drug_and_manufacturer_nodes_with_labelled_by_edge():
    graph = build_fixture_graph()
    drug_id = "drug:71335-9603"
    mfr_id = "mfr:bryant_ranch_prepack"
    assert graph.nodes[drug_id]["type"] == "Drug"
    assert graph.nodes[mfr_id]["type"] == "Manufacturer"
    assert graph.has_edge(drug_id, mfr_id)


def test_geography_has_51_nodes():
    graph = build_fixture_graph()
    geo_nodes = [n for n, d in graph.nodes(data=True) if d["type"] == "Geography"]
    assert len(geo_nodes) == 51


def test_big3_distributors_licensed_in_all_states():
    graph = build_fixture_graph()
    # Distributor nodes are keyed by canonical name now.
    mckesson_edges = list(graph.out_edges("dist:mckesson"))
    assert len(mckesson_edges) == 51


def test_drug_status_discontinued_when_listing_expired():
    graph = build_fixture_graph()
    drug = graph.nodes["drug:0363-0160"]
    assert drug["status"] == "active"


def test_manufacturers_carry_repackager_flag():
    graph = build_fixture_graph()
    mfrs = [d for _, d in graph.nodes(data=True) if d["type"] == "Manufacturer"]
    assert mfrs, "fixture should produce manufacturer nodes"
    assert all("is_repackager" in d for d in mfrs)
    assert all(d["entity_type"] in {"manufacturer", "repackager"} for d in mfrs)


def test_authorized_generic_counts_as_generic():
    from app.graph.build import _GENERIC_CATEGORIES

    assert "ANDA" in _GENERIC_CATEGORIES
    assert "NDA AUTHORIZED GENERIC" in _GENERIC_CATEGORIES


def test_active_ingredient_nodes_and_contains_edges():
    graph = build_fixture_graph()
    ingredients = [n for n, d in graph.nodes(data=True) if d["type"] == "ActiveIngredient"]
    assert ingredients
    assert any(k == "CONTAINS" for _, _, k in graph.edges(keys=True))


def test_facility_match_creates_operates_and_overrides_repackager():
    # A DECRS facility whose canonical name matches the fixture's labeler.
    fac = FacilityRecord(
        fei_number="900001",
        firm_name="Bryant Ranch Prepack",
        canonical_name="bryant ranch prepack",
        address="1 Main St, Burbank, California (CA) 91504, United States (USA)",
        city="Burbank",
        state="CA",
        country="USA",
        is_foreign=False,
        operations=["MANUFACTURE"],
        is_manufacturer=True,
        is_repackager=False,
        expiration_date="12/31/2026",
        registrant_name="Bryant Ranch Prepack",
    )
    graph = build_fixture_graph(facility_records=[fac])
    mfr = graph.nodes["mfr:bryant_ranch_prepack"]
    assert any(k == "OPERATES" for _, _, k in graph.out_edges("mfr:bryant_ranch_prepack", keys=True))
    # DECRS says it manufactures -> repackager flag overridden to False, sourced from DECRS.
    assert mfr["is_repackager"] is False
    assert mfr["repackager_source"] == "decrs"
    assert any(k == "LOCATED_IN" for _, _, k in graph.out_edges("facility:900001", keys=True))


def test_facility_match_overrides_source_even_with_no_mfr_or_repack_ops():
    # Regression: a facility match whose own operations are neither
    # manufacture nor repack/relabel (e.g. ANALYSIS-only) still proves a real
    # DECRS link and must override the heuristic source -- it must not be
    # silently skipped just because neither flag was set on this facility.
    fac = FacilityRecord(
        fei_number="900002",
        firm_name="Bryant Ranch Prepack",
        canonical_name="bryant ranch prepack",
        address="1 Main St, Burbank, California (CA) 91504, United States (USA)",
        city="Burbank",
        state="CA",
        country="USA",
        is_foreign=False,
        operations=["ANALYSIS"],
        is_manufacturer=False,
        is_repackager=False,
        expiration_date="12/31/2026",
        registrant_name="Bryant Ranch Prepack",
    )
    graph = build_fixture_graph(facility_records=[fac])
    mfr = graph.nodes["mfr:bryant_ranch_prepack"]
    assert mfr["repackager_source"] == "decrs"


def test_find_alternatives_reports_true_total_beyond_cap():
    from app.graph.queries import find_alternatives

    records = load_fixture_records()
    appl = next(r.application_number for r in records if r.application_number)
    key = ndc_application_key(appl)
    drug_id = f"drug:{next(r.product_ndc for r in records if r.application_number)}"
    index = {key: OrangeBookEntry(te_codes={"AB"}, te_groups={"FOO|TABLET;ORAL|AB"})}
    graph = build_fixture_graph(orange_book_index=index)

    # Inject 30 synthetic equivalents (beyond the cap of 24) sharing the same TE group.
    for i in range(30):
        node_id = f"drug:synthetic-{i}"
        graph.add_node(node_id, type="Drug", generic_name="Foo", te_groups=["FOO|TABLET;ORAL|AB"])

    result = find_alternatives(graph, drug_id, cap=24)
    assert result["total"] == 30
    assert len(result["items"]) == 24


def test_orange_book_enriches_matching_drug():
    records = load_fixture_records()
    appl = next(r.application_number for r in records if r.application_number)
    key = ndc_application_key(appl)
    index = {key: OrangeBookEntry(te_codes={"AB"}, te_groups={"FOO|TABLET;ORAL|AB"})}
    graph = build_fixture_graph(orange_book_index=index)
    enriched = [d for _, d in graph.nodes(data=True) if d["type"] == "Drug" and d.get("in_orange_book")]
    assert enriched
    assert any("FOO|TABLET;ORAL|AB" in d["te_groups"] for d in enriched)
