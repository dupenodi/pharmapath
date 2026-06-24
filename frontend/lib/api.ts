import type { QueryResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
