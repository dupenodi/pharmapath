from datetime import datetime, timezone

import networkx as nx


class GraphStore:
    """Holds the in-memory networkx graph and seeding metadata.

    Populated by the Phase 2 ingestion pipeline. Phase 0 only needs the
    shape of this object so /health can report on it before the graph exists.
    """

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.seeded_at: datetime | None = None

    @property
    def is_loaded(self) -> bool:
        return self.seeded_at is not None

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def mark_seeded(self) -> None:
        self.seeded_at = datetime.now(timezone.utc)


graph_store = GraphStore()
