import re
from collections import Counter, defaultdict

import networkx as nx
from rapidfuzz import fuzz

_WORD_SPLIT = re.compile(r"[\s,\-/;]+")
FUZZY_THRESHOLD = 80.0

# Edge kinds that make up a drug's supply chain, per PLAN.md's graph schema.
# Facility/Geography/ActiveIngredient branches stay empty until DECRS/label
# data is ingested (Phase 3+), but the traversal already supports them.
SUPPLY_CHAIN_EDGE_KINDS = ("CONTAINS", "LABELLED_BY", "OPERATES", "LOCATED_IN")

# The canonical distribution-chain schema from PLAN.md, in flow order. The
# overview endpoint reports this so the UI can render the *expected* shape and
# grey out node/edge types that have no data yet -- making gaps obvious.
SCHEMA_NODE_TYPES = (
    "ActiveIngredient",
    "Drug",
    "Manufacturer",
    "Facility",
    "Distributor",
    "Geography",
    "ComplianceFlag",
    "Shortage",
)
SCHEMA_EDGES = (
    ("Drug", "ActiveIngredient", "CONTAINS"),
    ("Drug", "Manufacturer", "LABELLED_BY"),
    ("Manufacturer", "Facility", "OPERATES"),
    ("Facility", "Geography", "LOCATED_IN"),
    ("Distributor", "Geography", "LICENSED_IN"),
    ("Manufacturer", "ComplianceFlag", "HAS_FLAG"),
    ("Drug", "Shortage", "HAS_SHORTAGE"),
)


def node_label(node_id: str, attrs: dict) -> str:
    return (
        attrs.get("brand_name")
        or attrs.get("name")
        or attrs.get("canonical_name")
        or attrs.get("generic_name")
        or node_id
    )


def serialize_node(graph: nx.MultiDiGraph, node_id: str) -> dict | None:
    if not graph.has_node(node_id):
        return None
    return {"id": node_id, **graph.nodes[node_id]}


def serialize_node_edges(graph: nx.MultiDiGraph, node_id: str) -> list[dict]:
    edges = []
    for _, target, key, data in graph.out_edges(node_id, keys=True, data=True):
        edges.append({"source": node_id, "target": target, "type": key, **data})
    for source, _, key, data in graph.in_edges(node_id, keys=True, data=True):
        edges.append({"source": source, "target": node_id, "type": key, **data})
    return edges


def get_supply_chain(graph: nx.MultiDiGraph, drug_id: str) -> dict | None:
    """BFS outward from a Drug node along supply-chain edge kinds.

    Returns {"nodes": [...], "edges": [...]} or None if the drug isn't found.
    """
    if not graph.has_node(drug_id):
        return None

    visited_nodes = {drug_id}
    visited_edges: list[dict] = []
    frontier = [drug_id]

    while frontier:
        next_frontier = []
        for node_id in frontier:
            for _, target, key, data in graph.out_edges(node_id, keys=True, data=True):
                if key not in SUPPLY_CHAIN_EDGE_KINDS:
                    continue
                visited_edges.append({"source": node_id, "target": target, "type": key, **data})
                if target not in visited_nodes:
                    visited_nodes.add(target)
                    next_frontier.append(target)
        frontier = next_frontier

    nodes = [serialize_node(graph, n) for n in visited_nodes]
    return {"nodes": nodes, "edges": visited_edges}


def get_neighborhood(graph: nx.MultiDiGraph, node_id: str, neighbor_cap: int = 60) -> dict | None:
    """1-hop neighborhood of a node as a renderable {nodes, edges} subgraph.

    High-degree hubs (a labeler with thousands of drugs) are capped so the UI
    stays responsive; `truncated`/`total_degree` report when that happened.
    """
    if not graph.has_node(node_id):
        return None

    seen = {node_id}
    edges: list[dict] = []
    total_degree = graph.degree(node_id)

    # out-edges then in-edges, stopping once we hit the cap of distinct neighbors.
    for src, tgt, key, data in graph.out_edges(node_id, keys=True, data=True):
        if len(seen) > neighbor_cap and tgt not in seen:
            continue
        seen.add(tgt)
        edges.append({"source": src, "target": tgt, "type": key, **data})
    for src, tgt, key, data in graph.in_edges(node_id, keys=True, data=True):
        if len(seen) > neighbor_cap and src not in seen:
            continue
        seen.add(src)
        edges.append({"source": src, "target": tgt, "type": key, **data})

    nodes = [serialize_node(graph, n) for n in seen]
    return {
        "nodes": nodes,
        "edges": edges,
        "focus": node_id,
        "total_degree": total_degree,
        "truncated": total_degree > len(seen) - 1,
    }


def node_type_counts(graph: nx.MultiDiGraph) -> dict[str, int]:
    return dict(Counter(d.get("type", "Unknown") for _, d in graph.nodes(data=True)))


def edge_type_counts(graph: nx.MultiDiGraph) -> dict[str, int]:
    return dict(Counter(k for _, _, k in graph.edges(keys=True)))


def meta_edges(graph: nx.MultiDiGraph) -> list[dict]:
    """Aggregate every edge to (source_type, edge_type, target_type) with a count.

    This is the 'schema-level' graph: how the node *types* actually connect in
    the loaded data, regardless of how many individual nodes there are.
    """
    counts: Counter[tuple[str, str, str]] = Counter()
    for source, target, key in graph.edges(keys=True):
        st = graph.nodes[source].get("type", "Unknown")
        tt = graph.nodes[target].get("type", "Unknown")
        counts[(st, key, tt)] += 1
    return [
        {"source_type": st, "type": key, "target_type": tt, "count": c}
        for (st, key, tt), c in sorted(counts.items(), key=lambda x: -x[1])
    ]


def _components_summary(graph: nx.MultiDiGraph) -> dict:
    """Weakly-connected components, with the dominant node type of each."""
    comps = list(nx.weakly_connected_components(graph))
    summary = []
    for comp in sorted(comps, key=len, reverse=True):
        types = Counter(graph.nodes[n].get("type", "Unknown") for n in comp)
        summary.append({"size": len(comp), "node_types": dict(types)})
    return {"count": len(comps), "components": summary[:20]}


def data_quality_report(graph: nx.MultiDiGraph) -> list[dict]:
    """Surface gaps that matter before we build agent tools on this graph.

    Each item: {level: 'error'|'warning'|'info', message, detail}. The goal is to
    make 'is the data strong enough?' answerable at a glance.
    """
    report: list[dict] = []
    type_counts = node_type_counts(graph)

    for expected in SCHEMA_NODE_TYPES:
        if type_counts.get(expected, 0) == 0:
            report.append(
                {
                    "level": "warning",
                    "message": f"No {expected} nodes in the graph yet",
                    "detail": f"The schema defines {expected}, but nothing has been ingested for it.",
                }
            )

    # Connectivity: is the distribution chain actually end-to-end?
    comps = _components_summary(graph)
    if comps["count"] > 1:
        # Do Distributors share a component with Drugs/Manufacturers?
        dist_with_supply = False
        for comp in comps["components"]:
            t = comp["node_types"]
            if "Distributor" in t and ("Drug" in t or "Manufacturer" in t):
                dist_with_supply = True
                break
        if not dist_with_supply and type_counts.get("Distributor", 0):
            report.append(
                {
                    "level": "error",
                    "message": "Distributors are not connected to any Drug or Manufacturer",
                    "detail": (
                        "Distributors only link to Geography (LICENSED_IN) and drugs only link to "
                        "Manufacturers (LABELLED_BY). There is no edge tying a product/manufacturer to a "
                        "distributor, so the chain is two disconnected halves. Sourcing queries can't "
                        "traverse drug -> distributor yet."
                    ),
                }
            )
        report.append(
            {
                "level": "info",
                "message": f"Graph splits into {comps['count']} disconnected components",
                "detail": "End-to-end traversal across the full chain isn't possible until they're linked.",
            }
        )

    # Manufacturer vs repackager split: repackagers aren't drug makers, so a
    # large share signals "manufacturer" answers are really repackager noise.
    mfrs = [d for _, d in graph.nodes(data=True) if d.get("type") == "Manufacturer"]
    if mfrs:
        repackagers = sum(1 for d in mfrs if d.get("is_repackager"))
        report.append(
            {
                "level": "info" if repackagers else "warning",
                "message": f"{len(mfrs):,} Manufacturer nodes ({repackagers:,} flagged as repackagers)",
                "detail": (
                    "Repackagers/relabelers are annotated (is_repackager=true) so they can be "
                    "excluded from true-manufacturer answers. DECRS facility_type would make this "
                    "authoritative."
                    if repackagers
                    else "No repackagers flagged yet -- expected ~24% of NDC labelers are repackagers."
                ),
            }
        )

    # Field completeness on Drug nodes.
    drugs = [d for _, d in graph.nodes(data=True) if d.get("type") == "Drug"]
    if drugs:
        missing_brand = sum(1 for d in drugs if not d.get("brand_name"))
        missing_strength = sum(1 for d in drugs if not d.get("strength"))
        missing_form = sum(1 for d in drugs if not d.get("dosage_form"))
        report.append(
            {
                "level": "info",
                "message": f"{len(drugs):,} Drug nodes loaded",
                "detail": (
                    f"{missing_brand:,} missing brand_name, {missing_strength:,} missing strength, "
                    f"{missing_form:,} missing dosage_form."
                ),
            }
        )

    return report


def graph_overview(graph: nx.MultiDiGraph) -> dict:
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "node_counts": node_type_counts(graph),
        "edge_counts": edge_type_counts(graph),
        "schema_node_types": list(SCHEMA_NODE_TYPES),
        "schema_edges": [
            {"source_type": s, "target_type": t, "type": k} for s, t, k in SCHEMA_EDGES
        ],
        "meta_edges": meta_edges(graph),
        "components": _components_summary(graph),
        "quality": data_quality_report(graph),
    }


# Plain-language relationship labels from the focal node's point of view,
# keyed by (focal_type, direction, edge_kind). "*" matches any focal type.
_RELATION_LABELS: dict[tuple[str, str, str], str] = {
    ("Drug", "out", "LABELLED_BY"): "Made by",
    ("Drug", "out", "CONTAINS"): "Active ingredients",
    ("Drug", "out", "HAS_SHORTAGE"): "Shortages",
    ("Manufacturer", "in", "LABELLED_BY"): "Products",
    ("Manufacturer", "out", "OPERATES"): "Facilities",
    ("Manufacturer", "out", "HAS_FLAG"): "Compliance flags",
    ("Facility", "in", "OPERATES"): "Operated by",
    ("Facility", "out", "LOCATED_IN"): "Location",
    ("Distributor", "out", "LICENSED_IN"): "Licensed in",
    ("ActiveIngredient", "in", "CONTAINS"): "Found in",
    ("Geography", "in", "LICENSED_IN"): "Distributors licensed here",
    ("Geography", "in", "LOCATED_IN"): "Facilities here",
}

_GROUP_CAP = 60  # neighbors shown per relationship before truncating


def _neighbor_caption(attrs: dict) -> str:
    """A short secondary line describing a neighbor, tuned per node type."""
    t = attrs.get("type")
    if t == "Drug":
        bits = [attrs.get("strength"), attrs.get("dosage_form")]
        return " · ".join(b for b in bits if b)
    if t == "Manufacturer":
        return "Repackager" if attrs.get("is_repackager") else "Manufacturer"
    if t == "Facility":
        loc = ", ".join(b for b in [attrs.get("city"), attrs.get("state")] if b)
        ops = ", ".join((attrs.get("operations") or [])[:3]).title()
        return " · ".join(b for b in [loc, ops] if b)
    if t == "Distributor":
        kind = "3PL" if attrs.get("distributor_type") == "third_party_logistics" else "Wholesaler"
        n = len(attrs.get("states_licensed") or [])
        return f"{kind} · licensed in {n} state{'s' if n != 1 else ''}"
    if t == "Geography":
        return attrs.get("region", "")
    return ""


def find_alternatives(graph: nx.MultiDiGraph, drug_id: str, cap: int = 24) -> dict:
    """Therapeutic equivalents: other drugs sharing an Orange Book TE group.

    Returns {"items": [...capped...], "total": <true count>} -- the total is
    never truncated, so the UI can always say "24 of 336" instead of silently
    presenting a capped list as if it were the complete set.
    """
    if not graph.has_node(drug_id):
        return {"items": [], "total": 0}
    groups = set(graph.nodes[drug_id].get("te_groups") or [])
    if not groups:
        return {"items": [], "total": 0}
    items: list[dict] = []
    total = 0
    for n, d in graph.nodes(data=True):
        if d.get("type") != "Drug" or n == drug_id:
            continue
        if groups & set(d.get("te_groups") or []):
            total += 1
            if len(items) < cap:
                items.append(
                    {
                        "id": n,
                        "label": node_label(n, d),
                        "type": "Drug",
                        "caption": _neighbor_caption(d),
                        "is_generic": d.get("is_generic", False),
                    }
                )
    return {"items": items, "total": total}


def get_entity_detail(graph: nx.MultiDiGraph, node_id: str) -> dict | None:
    """A type-aware, human-readable record for one node: its own attributes plus
    its relationships grouped under plain-language labels (the 'monograph')."""
    if not graph.has_node(node_id):
        return None
    attrs = graph.nodes[node_id]
    focal_type = attrs.get("type", "")

    grouped: dict[str, dict] = {}

    def add(direction: str, edge_key: str, neighbor_id: str) -> None:
        label = (
            _RELATION_LABELS.get((focal_type, direction, edge_key))
            or _RELATION_LABELS.get(("*", direction, edge_key))
            or edge_key.replace("_", " ").title()
        )
        g = grouped.setdefault(label, {"relation": label, "items": [], "total": 0})
        g["total"] += 1
        if len(g["items"]) < _GROUP_CAP:
            n = graph.nodes[neighbor_id]
            g["items"].append(
                {
                    "id": neighbor_id,
                    "label": node_label(neighbor_id, n),
                    "type": n.get("type", ""),
                    "caption": _neighbor_caption(n),
                }
            )

    for _, tgt, key in graph.out_edges(node_id, keys=True):
        add("out", key, tgt)
    for src, _, key in graph.in_edges(node_id, keys=True):
        add("in", key, src)

    connections = list(grouped.values())
    if focal_type == "Drug":
        alts = find_alternatives(graph, node_id)
        if alts["total"]:
            connections.append(
                {"relation": "Therapeutic equivalents", "items": alts["items"], "total": alts["total"]}
            )

    return {
        "node": {"id": node_id, **attrs},
        "label": node_label(node_id, attrs),
        "type": focal_type,
        "connections": connections,
    }


def _fuzzy_word_match(query: str, label: str) -> float:
    """Best similarity between the query and any single word in label.

    Word-level (not whole-label or arbitrary-substring) so a short word can't
    trivially "contain" the query the way partial-substring matching would --
    that previously let nonsense like "tin" score 100% against "atorvastin".
    """
    words = [w for w in _WORD_SPLIT.split(label) if w]
    if not words:
        return 0.0
    return max(fuzz.ratio(query, w) for w in words)


def list_nodes(
    graph: nx.MultiDiGraph,
    node_type: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated, searchable listing of nodes -- the backbone of the explorer.

    Lets the UI inspect every one of the ~58k nodes without ever shipping them
    all at once. Substring matches are sorted by degree (most-connected first)
    so the hubs of the chain surface naturally. If a query has zero substring
    matches (e.g. a typo), we fall back to fuzzy word matching so close
    misspellings still find something instead of "no results".
    """
    q = (query or "").strip().lower()
    matches: list[tuple[str, dict, int]] = []
    for node_id, attrs in graph.nodes(data=True):
        if node_type and attrs.get("type") != node_type:
            continue
        if q:
            label = str(node_label(node_id, attrs)).lower()
            if q not in label and q not in node_id.lower():
                continue
        degree = graph.degree(node_id)
        matches.append((node_id, attrs, degree))

    fuzzy = False
    if q and not matches:
        fuzzy = True
        scored: list[tuple[str, dict, float]] = []
        for node_id, attrs in graph.nodes(data=True):
            if node_type and attrs.get("type") != node_type:
                continue
            score = _fuzzy_word_match(q, str(node_label(node_id, attrs)).lower())
            if score >= FUZZY_THRESHOLD:
                scored.append((node_id, attrs, score))
        scored.sort(key=lambda m: m[2], reverse=True)
        matches = [(node_id, attrs, graph.degree(node_id)) for node_id, attrs, _ in scored]
    else:
        matches.sort(key=lambda m: m[2], reverse=True)

    total = len(matches)
    page = matches[offset : offset + limit]
    items = [
        {
            "id": node_id,
            "type": attrs.get("type", "Unknown"),
            "label": node_label(node_id, attrs),
            "degree": degree,
            "attrs": attrs,
        }
        for node_id, attrs, degree in page
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items, "fuzzy": fuzzy}
