from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.graph.store import graph_store
from tests.test_graph_build import build_fixture_graph

client = TestClient(app)


def seed_fixture_graph():
    graph_store.graph = build_fixture_graph()
    graph_store.seeded_at = datetime.now(timezone.utc)


def test_health_reflects_seeded_graph():
    seed_fixture_graph()
    response = client.get("/health")
    body = response.json()
    assert body["graph_loaded"] is True
    assert body["node_count"] > 0


def test_get_node_returns_404_for_unknown_node():
    seed_fixture_graph()
    response = client.get("/graph/node/drug:does-not-exist")
    assert response.status_code == 404


def test_get_node_returns_drug_and_its_edges():
    seed_fixture_graph()
    response = client.get("/graph/node/drug:71335-9603")
    assert response.status_code == 200
    body = response.json()
    assert body["node"]["type"] == "Drug"
    assert any(e["type"] == "LABELLED_BY" for e in body["edges"])


def test_supply_chain_includes_manufacturer():
    seed_fixture_graph()
    response = client.get("/graph/supply-chain/drug:71335-9603")
    assert response.status_code == 200
    body = response.json()
    node_ids = {n["id"] for n in body["nodes"]}
    assert "drug:71335-9603" in node_ids
    assert "mfr:bryant_ranch_prepack" in node_ids


def test_overview_reports_counts_schema_and_quality():
    seed_fixture_graph()
    body = client.get("/graph/overview").json()
    assert body["node_count"] > 0
    assert body["node_counts"]["Drug"] > 0
    assert body["node_counts"]["Manufacturer"] > 0
    assert "LABELLED_BY" in body["edge_counts"]
    assert set(body["schema_node_types"]) >= {"Drug", "Manufacturer", "Distributor", "Geography"}
    assert any(m["type"] == "LABELLED_BY" for m in body["meta_edges"])
    # The fixture chain is disconnected (distributors only link to geography),
    # so the quality report should flag it as an error.
    assert any(item["level"] == "error" for item in body["quality"])


def test_entity_detail_groups_relationships_for_a_drug():
    seed_fixture_graph()
    body = client.get("/graph/entity/drug:71335-9603").json()
    assert body["type"] == "Drug"
    relations = {c["relation"] for c in body["connections"]}
    assert "Made by" in relations
    assert "Active ingredients" in relations


def test_entity_detail_404_for_unknown():
    seed_fixture_graph()
    assert client.get("/graph/entity/drug:nope").status_code == 404


def test_nodes_listing_filters_by_type_and_search():
    seed_fixture_graph()
    body = client.get("/graph/nodes", params={"type": "Manufacturer", "limit": 5}).json()
    assert body["total"] >= 1
    assert all(item["type"] == "Manufacturer" for item in body["items"])
    assert len(body["items"]) <= 5

    geo = client.get("/graph/nodes", params={"type": "Geography", "q": "california"}).json()
    assert geo["total"] == 1
    assert geo["items"][0]["id"] == "geo:CA"


def test_nodes_listing_falls_back_to_fuzzy_match_on_typo():
    seed_fixture_graph()
    # "acetaminphen" (missing the second "o") has no substring match, so this
    # should fall back to fuzzy word matching and still find Acetaminophen.
    body = client.get("/graph/nodes", params={"q": "acetaminphen"}).json()
    assert body["total"] > 0
    assert body["fuzzy"] is True
    assert any("Acetaminophen" in item["label"] for item in body["items"])


def test_nodes_listing_exact_substring_match_is_not_marked_fuzzy():
    seed_fixture_graph()
    body = client.get("/graph/nodes", params={"q": "acetaminophen"}).json()
    assert body["total"] > 0
    assert body["fuzzy"] is False
