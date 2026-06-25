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


def _add_drug(graph, node_id, generic_name, strength="10 mg/1", dosage_form="TABLET", brand_name=None):
    graph.add_node(
        node_id,
        type="Drug",
        status="active",
        generic_name=generic_name,
        brand_name=brand_name,
        strength=strength,
        dosage_form=dosage_form,
        is_generic=brand_name is None,
        substance_name=[generic_name],
    )


def test_typo_resolves_via_word_level_fuzzy_match_without_noise():
    graph = build_test_graph()
    _add_drug(graph, "drug:atorva-1", "Atorvastatin Calcium", strength="80 mg/1")
    _add_drug(graph, "drug:atorva-2", "Atorvastatin Calcium", strength="20 mg/1")
    # Unrelated drugs that should NOT match a typo'd "atorvastin".
    _add_drug(graph, "drug:noise-1", "Naftin")
    _add_drug(graph, "drug:noise-2", "Tigan")

    result = resolve_drug(graph, "atorvastin")
    assert set(result.drug_ids) >= {"drug:atorva-1", "drug:atorva-2"}
    assert "drug:noise-1" not in result.drug_ids
    assert "drug:noise-2" not in result.drug_ids


def test_messy_sentence_input_does_not_explode_into_unrelated_matches():
    # Regression: a model once passed a full sentence (including a stray
    # drug ID and dosage) as drug_name and got back ~1,880 unrelated drugs
    # because whole-string fuzzy matching let filler words like "drug" and
    # "with" coincidentally match unrelated product names.
    graph = build_test_graph()
    _add_drug(graph, "drug:atorva-1", "Atorvastatin Calcium", strength="80 mg/1")
    _add_drug(graph, "drug:unrelated", "Discount Drug Mart Mouthwash")

    result = resolve_drug(graph, "let's go with the 80mg tablet, drug id drug:atorva-1")
    assert "drug:unrelated" not in result.drug_ids


def test_disambiguation_options_capped_with_true_total_reported():
    graph = build_test_graph()
    for i in range(20):
        _add_drug(graph, f"drug:atorva-{i}", "Atorvastatin Calcium", strength=f"{i + 1} mg/1")

    result = resolve_drug(graph, "Atorvastatin Calcium")
    assert result.ambiguous is True
    assert len(result.disambiguation_options) <= 12
    assert result.disambiguation_total == 20
