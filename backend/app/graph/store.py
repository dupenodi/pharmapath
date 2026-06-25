from datetime import datetime, timezone

import networkx as nx

from app.graph.build import build_graph
from app.ingestion.decrs import load_facility_records
from app.ingestion.distributors import load_distributor_records
from app.ingestion.geography import load_geography_records
from app.ingestion.ndc import dedupe_ndc_records, load_ndc_records
from app.ingestion.orange_book import load_orange_book_index


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
        # Both prescription and OTC drugs -- excluding OTC left common products
        # like Tylenol or Advil invisible with no explanation (PLAN.md never
        # required excluding them, just de-prioritized them for phase 1).
        in_scope = {"HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"}
        ndc_records = dedupe_ndc_records([r for r in load_ndc_records() if r.product_type in in_scope])
        self.graph = build_graph(
            ndc_records=ndc_records,
            distributor_records=load_distributor_records(),
            geography_records=load_geography_records(),
            facility_records=load_facility_records(),
            orange_book_index=load_orange_book_index(),
        )
        self.seeded_at = datetime.now(timezone.utc)


graph_store = GraphStore()
