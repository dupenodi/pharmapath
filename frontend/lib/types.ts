export type ComplianceFlag = {
  id: string;
  flag_type: string;
  severity: "critical" | "high" | "medium" | "low";
  status: "active" | "closed";
  issued_date: string | null;
  closed_date: string | null;
  description: string;
  source_url: string | null;
  affected_products: string[];
};

export type Shortage = {
  id: string;
  drug_name: string;
  generic_name: string;
  status: "active" | "resolved";
  reason: string | null;
  start_date: string | null;
  resolved_date: string | null;
  affected_firms: string[];
  source: string;
  last_checked: string;
};

export type SupplierMatch = {
  supplier_id: string;
  supplier_name: string;
  supplier_type: "distributor" | "manufacturer_direct";
  score: number;
  compliance_status: "clean" | "flagged" | "unknown";
  active_flags: ComplianceFlag[];
  licensed_in_state: boolean;
  states_licensed: string[];
  shortage_risk: "none" | "possible" | "confirmed";
  distance_km: number | null;
  score_breakdown: { compliance: number; availability: number; location: number; coverage: number };
  caveats: string[];
};

export type RiskSummary = {
  overall_risk: "low" | "medium" | "high" | "critical";
  shortage_active: boolean;
  manufacturers_flagged: number;
  manufacturers_total: number;
  risk_flags: string[];
};

export type GraphNode = { id: string; type: string; [key: string]: unknown };
export type GraphEdge = { source: string; target: string; type: string; [key: string]: unknown };

export type Distributor = {
  id: string;
  type: "Distributor";
  name: string;
  canonical_name: string;
  distributor_type: string;
  home_state: string;
  city: string;
  states_licensed: string[];
  national_coverage: boolean;
};

export type DisambiguationOption = { drug_id: string; label: string };

export type ComponentName =
  | "supply_chain_graph"
  | "supplier_table"
  | "risk_card"
  | "map_view"
  | "comparison_card"
  | "disambiguation_prompt";

export type SupplyChainGraphData = { nodes: GraphNode[]; edges: GraphEdge[] };
export type SupplierTableData = { matches: SupplierMatch[]; explanation: string };
export type RiskCardData = { drug_name?: string; risk_summary: RiskSummary | null; shortages?: Shortage[] };
export type MapViewData = { state: string; distributors: Distributor[] };
export type ComparisonCardData = { left: Record<string, unknown>; right: Record<string, unknown> };
export type DisambiguationPromptData = { query?: string; options: DisambiguationOption[] };

export type ToolCall = { name: string; input: Record<string, unknown>; result: unknown };

export type QueryResponse = {
  agent_response: string;
  component: ComponentName | null;
  component_data: Record<string, unknown> | null;
  tool_calls: ToolCall[];
  warnings: string[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  component: ComponentName | null;
  componentData: Record<string, unknown> | null;
  warnings: string[];
};
