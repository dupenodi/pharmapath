import networkx as nx

# Edge kinds that make up a drug's supply chain, per PLAN.md's graph schema.
# Facility/Geography/ActiveIngredient branches stay empty until DECRS/label
# data is ingested (Phase 3+), but the traversal already supports them.
SUPPLY_CHAIN_EDGE_KINDS = ("CONTAINS", "LABELLED_BY", "OPERATES", "LOCATED_IN")


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
