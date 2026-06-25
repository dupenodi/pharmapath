from app.core.config import settings
from app.graph import store as store_module
from app.graph.store import GraphStore
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from tests.test_graph_build import load_fixture_records


def _patch_loaders(monkeypatch):
    monkeypatch.setattr(store_module, "load_ndc_records", load_fixture_records)
    monkeypatch.setattr(store_module, "load_distributor_records", load_big3_distributors)
    monkeypatch.setattr(store_module, "load_geography_records", load_geography_records)
    monkeypatch.setattr(store_module, "load_facility_records", lambda: [])
    monkeypatch.setattr(store_module, "load_orange_book_index", lambda: {})


def test_seed_includes_both_prescription_and_otc_drugs(monkeypatch):
    # The fixture has one HUMAN OTC DRUG (Walgreens Acetaminophen) and one
    # HUMAN PRESCRIPTION DRUG record -- seed() must keep both, not just Rx.
    _patch_loaders(monkeypatch)

    store = GraphStore()
    store.seed()

    drugs = [d for _, d in store.graph.nodes(data=True) if d.get("type") == "Drug"]
    assert any(d.get("otc") for d in drugs), "OTC drug should be present after seeding"
    assert any(not d.get("otc") for d in drugs), "Prescription drug should be present after seeding"


def test_seed_rx_only_scope_excludes_otc_drugs(monkeypatch):
    # GRAPH_SCOPE=rx_only is the memory-constrained-hosting mode -- must
    # actually drop OTC records, not just ignore the setting.
    _patch_loaders(monkeypatch)
    monkeypatch.setattr(settings, "graph_scope", "rx_only")

    store = GraphStore()
    store.seed()

    drugs = [d for _, d in store.graph.nodes(data=True) if d.get("type") == "Drug"]
    assert drugs, "Prescription drug should still be present"
    assert all(not d.get("otc") for d in drugs), "rx_only scope must exclude OTC drugs"
