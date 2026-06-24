from datetime import datetime, timezone

import networkx as nx

from app.graph.build import build_graph
from app.ingestion.distributors_big3 import load_big3_distributors
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import load_ndc_records


class GraphStore:
    """Holds the in-memory networkx graph and seeding metadata."""

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

    def seed(self) -> None:
        ndc_records = [r for r in load_ndc_records() if r.product_type == "HUMAN PRESCRIPTION DRUG"]
        self.graph = build_graph(
            ndc_records=ndc_records,
            distributor_records=load_big3_distributors(),
            geography_records=load_geography_records(),
        )
        self.seeded_at = datetime.now(timezone.utc)


graph_store = GraphStore()
