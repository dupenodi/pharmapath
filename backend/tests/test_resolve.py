import json
from pathlib import Path

from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import parse_ndc_records
from app.matching.resolve import resolve_drug

FIXTURE = Path(__file__).parent / "fixtures" / "ndc_sample.json"


def build_test_graph():
    with FIXTURE.open() as f:
        records = parse_ndc_records(json.load(f))
    return build_graph(
        ndc_records=records,
        distributor_records=load_big3_distributors(),
        geography_records=load_geography_records(),
    )


def test_resolves_exact_generic_name():
    graph = build_test_graph()
    result = resolve_drug(graph, "Butalbital, Acetaminophen and Caffeine")
    assert result.drug_ids == ["drug:71335-9603"]
    assert result.ambiguous is False


def test_unmatched_dosage_form_returns_no_results_instead_of_guessing():
    graph = build_test_graph()
    result = resolve_drug(graph, "Acetaminophen", dosage_form="INJECTION")
    assert result.drug_ids == []
    assert result.ambiguous is False


def test_unmatched_strength_returns_no_results_instead_of_guessing():
    graph = build_test_graph()
    result = resolve_drug(graph, "Acetaminophen", strength="999mg")
    assert result.drug_ids == []
