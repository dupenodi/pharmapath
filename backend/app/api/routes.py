from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.loop import run_agent_turn
from app.graph.queries import get_supply_chain, serialize_node, serialize_node_edges
from app.graph.store import graph_store

router = APIRouter()


class QueryRequest(BaseModel):
    message: str
    session_id: str


@router.post("/query")
async def query(request: QueryRequest) -> dict:
    return await run_agent_turn(graph_store.graph, request.session_id, request.message)


@router.get("/health")
def health() -> dict:
    return {
        "graph_loaded": graph_store.is_loaded,
        "node_count": graph_store.node_count,
        "edge_count": graph_store.edge_count,
        "seeded_at": graph_store.seeded_at,
    }


@router.get("/graph/node/{node_id}")
def get_node(node_id: str) -> dict:
    node = serialize_node(graph_store.graph, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")
    return {"node": node, "edges": serialize_node_edges(graph_store.graph, node_id)}


@router.get("/graph/supply-chain/{drug_id}")
def get_drug_supply_chain(drug_id: str) -> dict:
    subgraph = get_supply_chain(graph_store.graph, drug_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"Drug {drug_id!r} not found")
    return subgraph
