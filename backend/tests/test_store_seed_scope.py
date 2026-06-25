from app.graph import store as store_module
from app.graph.store import GraphStore
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from tests.test_graph_build import load_fixture_records


def test_seed_includes_both_prescription_and_otc_drugs(monkeypatch):
    # The fixture has one HUMAN OTC DRUG (Walgreens Acetaminophen) and one
    # HUMAN PRESCRIPTION DRUG record -- seed() must keep both, not just Rx.
    monkeypatch.setattr(store_module, "load_ndc_records", load_fixture_records)
    monkeypatch.setattr(store_module, "load_distributor_records", load_big3_distributors)
    monkeypatch.setattr(store_module, "load_geography_records", load_geography_records)
    monkeypatch.setattr(store_module, "load_facility_records", lambda: [])
    monkeypatch.setattr(store_module, "load_orange_book_index", lambda: {})

    store = GraphStore()
    store.seed()

    drugs = [d for _, d in store.graph.nodes(data=True) if d.get("type") == "Drug"]
    assert any(d.get("otc") for d in drugs), "OTC drug should be present after seeding"
    assert any(not d.get("otc") for d in drugs), "Prescription drug should be present after seeding"
