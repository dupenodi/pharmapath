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
export type AlternativeDrug = { drug_id: string; generic_name: string; brand_name: string | null; relationship: string };
export type SupplierTableData = {
  matches: SupplierMatch[];
  matches_total?: number;
  explanation: string;
  alternatives?: AlternativeDrug[];
};
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

export type ConnectionItem = {
  id: string;
  label: string;
  type: string;
  caption: string;
  is_generic?: boolean;
};

export type ConnectionGroup = {
  relation: string;
  items: ConnectionItem[];
  total: number;
};

export type EntityDetail = {
  node: GraphNode;
  label: string;
  type: string;
  connections: ConnectionGroup[];
};

export type QualityItem = {
  level: "error" | "warning" | "info";
  message: string;
  detail: string;
};

export type MetaEdge = { source_type: string; type: string; target_type: string; count: number };

export type GraphOverview = {
  node_count: number;
  edge_count: number;
  node_counts: Record<string, number>;
  edge_counts: Record<string, number>;
  schema_node_types: string[];
  schema_edges: { source_type: string; target_type: string; type: string }[];
  meta_edges: MetaEdge[];
  components: { count: number; components: { size: number; node_types: Record<string, number> }[] };
  quality: QualityItem[];
};

export type NodeListItem = {
  id: string;
  type: string;
  label: string;
  degree: number;
  attrs: Record<string, unknown>;
};

export type NodeListResponse = {
  total: number;
  limit: number;
  offset: number;
  items: NodeListItem[];
  fuzzy?: boolean;
};

export type Neighborhood = SupplyChainGraphData & {
  focus: string;
  total_degree: number;
  truncated: boolean;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  component: ComponentName | null;
  componentData: Record<string, unknown> | null;
  warnings: string[];
};
