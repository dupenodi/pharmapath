import type { GraphNode } from "./types";

export type NodeMeta = { color: string; label: string };

// Keep these hex values in sync with the --node-* CSS variables in globals.css.
// Cytoscape renders to canvas and can't read CSS custom properties directly.
export const NODE_META: Record<string, NodeMeta> = {
  Drug: { color: "#5ba8ff", label: "Drug" },
  ActiveIngredient: { color: "#b79cff", label: "Ingredient" },
  Manufacturer: { color: "#34d399", label: "Manufacturer" },
  Facility: { color: "#2dd4bf", label: "Facility" },
  Distributor: { color: "#f4a259", label: "Distributor" },
  Geography: { color: "#94a3b8", label: "Location" },
  ComplianceFlag: { color: "#fb7185", label: "Compliance flag" },
  Shortage: { color: "#fb7185", label: "Shortage" },
};

// Relationship phrasing on edges, read in the direction source → target.
export const EDGE_LABEL: Record<string, string> = {
  CONTAINS: "contains",
  LABELLED_BY: "made by",
  OPERATES: "operates",
  LOCATED_IN: "located in",
  LICENSED_IN: "licensed in",
  HAS_FLAG: "flagged",
  HAS_SHORTAGE: "shortage",
};

export function typeColor(type: string): string {
  return NODE_META[type]?.color ?? "#71717a";
}

export function typeLabel(type: string): string {
  return NODE_META[type]?.label ?? type;
}

export function nodeColor(node: { type: string; is_repackager?: unknown; active_flags?: unknown }): string {
  if (node.type === "Manufacturer" && node.is_repackager) {
    return "#f4a259"; // repackagers read as logistics, not makers
  }
  if (node.type === "Manufacturer") {
    const hasActiveFlag = (node.active_flags as { status: string }[] | undefined)?.some(
      (f) => f.status === "active",
    );
    if (hasActiveFlag) return "#fb7185";
  }
  return typeColor(node.type);
}

export function nodeLabel(node: GraphNode): string {
  return (
    (node.brand_name as string) ||
    (node.name as string) ||
    (node.canonical_name as string) ||
    (node.generic_name as string) ||
    node.id
  );
}
