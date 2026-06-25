import type {
  EntityDetail,
  GraphOverview,
  Neighborhood,
  NodeListResponse,
  QueryResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

export async function postQuery(message: string, sessionId: string): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!response.ok) {
    throw new Error(`Query failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

export function fetchGraphOverview(): Promise<GraphOverview> {
  return getJSON<GraphOverview>("/graph/overview");
}

export function fetchGraphNodes(params: {
  type?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<NodeListResponse> {
  const search = new URLSearchParams();
  if (params.type) search.set("type", params.type);
  if (params.q) search.set("q", params.q);
  if (params.limit != null) search.set("limit", String(params.limit));
  if (params.offset != null) search.set("offset", String(params.offset));
  return getJSON<NodeListResponse>(`/graph/nodes?${search.toString()}`);
}

export function fetchNeighborhood(nodeId: string): Promise<Neighborhood> {
  return getJSON<Neighborhood>(`/graph/neighborhood/${encodeURIComponent(nodeId)}`);
}

export function fetchEntity(nodeId: string): Promise<EntityDetail> {
  return getJSON<EntityDetail>(`/graph/entity/${encodeURIComponent(nodeId)}`);
}
