import pytest

from app.graph.store import GraphStore, graph_store


@pytest.fixture(autouse=True)
def reset_graph_store():
    """Tests share the graph_store singleton; reset it so order doesn't matter."""
    fresh = GraphStore()
    graph_store.graph = fresh.graph
    graph_store.seeded_at = fresh.seeded_at
    yield
    graph_store.graph = fresh.graph
    graph_store.seeded_at = None
