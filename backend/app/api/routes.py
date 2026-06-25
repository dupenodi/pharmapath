import anthropic
import openai
from fastapi import APIRouter, HTTPException
from google.genai import errors as genai_errors
from pydantic import BaseModel

from app.agent.loop import run_agent_turn
from app.graph.queries import (
    get_entity_detail,
    get_neighborhood,
    get_supply_chain,
    graph_overview,
    list_nodes,
    serialize_node,
    serialize_node_edges,
)
from app.graph.store import graph_store

router = APIRouter()


class QueryRequest(BaseModel):
    message: str
    session_id: str


@router.post("/query")
async def query(request: QueryRequest) -> dict:
    try:
        return await run_agent_turn(graph_store.graph, request.session_id, request.message)
    except genai_errors.ClientError as e:
        if getattr(e, "code", None) == 429:
            raise HTTPException(
                status_code=429,
                detail="Gemini rate limit hit (free tier is 5 requests/minute for gemini-2.5-flash). Wait a minute and try again, or switch AGENT_PROVIDER to anthropic or openai.",
            ) from e
        raise
    except openai.RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"OpenAI rate limit hit ({e}). Wait a minute and try again, or switch AGENT_PROVIDER.",
        ) from e
    except (
        genai_errors.ServerError,
        anthropic.APIStatusError,
        anthropic.APIConnectionError,
        openai.APIStatusError,
        openai.APIConnectionError,
    ) as e:
        raise HTTPException(
            status_code=503,
            detail=f"The model provider is temporarily unavailable ({e}). Please try again in a moment.",
        ) from e


@router.get("/health")
def health() -> dict:
    return {
        "graph_loaded": graph_store.is_loaded,
        "node_count": graph_store.node_count,
        "edge_count": graph_store.edge_count,
        "seeded_at": graph_store.seeded_at,
    }


@router.get("/graph/overview")
def get_graph_overview() -> dict:
    """Schema-level shape, type/edge counts, connectivity, and data-quality report."""
    return graph_overview(graph_store.graph)


@router.get("/graph/nodes")
def get_graph_nodes(
    type: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated, searchable node inventory, optionally filtered by node type."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return list_nodes(graph_store.graph, node_type=type, query=q, limit=limit, offset=offset)


@router.get("/graph/node/{node_id}")
def get_node(node_id: str) -> dict:
    node = serialize_node(graph_store.graph, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")
    return {"node": node, "edges": serialize_node_edges(graph_store.graph, node_id)}


@router.get("/graph/entity/{node_id}")
def get_entity(node_id: str) -> dict:
    """Type-aware record for the detail panel: attributes + grouped relationships."""
    detail = get_entity_detail(graph_store.graph, node_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")
    return detail


@router.get("/graph/neighborhood/{node_id}")
def get_node_neighborhood(node_id: str) -> dict:
    subgraph = get_neighborhood(graph_store.graph, node_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")
    return subgraph


@router.get("/graph/supply-chain/{drug_id}")
def get_drug_supply_chain(drug_id: str) -> dict:
    subgraph = get_supply_chain(graph_store.graph, drug_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"Drug {drug_id!r} not found")
    return subgraph
