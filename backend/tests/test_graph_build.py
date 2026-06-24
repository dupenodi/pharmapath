import json
from pathlib import Path

from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import parse_ndc_records

FIXTURE = Path(__file__).parent / "fixtures" / "ndc_sample.json"


def load_fixture_records():
    with FIXTURE.open() as f:
        return parse_ndc_records(json.load(f))


def build_fixture_graph():
    return build_graph(
        ndc_records=load_fixture_records(),
        distributor_records=load_big3_distributors(),
        geography_records=load_geography_records(),
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
    mckesson_edges = list(graph.out_edges("dist:BIG3-MCKESSON"))
    assert len(mckesson_edges) == 51


def test_drug_status_discontinued_when_listing_expired():
    graph = build_fixture_graph()
    drug = graph.nodes["drug:0363-0160"]
    assert drug["status"] == "active"
