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
