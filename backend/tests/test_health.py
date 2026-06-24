from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_unseeded_graph_state():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["graph_loaded"] is False
    assert body["node_count"] == 0
    assert body["edge_count"] == 0
