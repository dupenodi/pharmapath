from fastapi import APIRouter

from app.graph.store import graph_store

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "graph_loaded": graph_store.is_loaded,
        "node_count": graph_store.node_count,
        "edge_count": graph_store.edge_count,
        "seeded_at": graph_store.seeded_at,
    }
