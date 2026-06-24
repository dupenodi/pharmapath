from datetime import date, datetime

import networkx as nx

from app.ingestion.models import DistributorRecord, GeographyRecord, NdcRecord
from app.ingestion.name_normalize import normalize_name


def _drug_status(listing_expiration_date: str | None) -> str:
    if not listing_expiration_date:
        return "active"
    try:
        expiry = datetime.strptime(listing_expiration_date, "%Y%m%d").date()
    except ValueError:
        return "active"
    return "active" if expiry >= date.today() else "discontinued"


def _manufacturer_id(canonical_name: str) -> str:
    slug = canonical_name.replace(" ", "_") or "unknown"
    return f"mfr:{slug}"


def add_ndc_records(graph: nx.MultiDiGraph, records: list[NdcRecord]) -> None:
    """Pipeline step 1: NDC -> Drug + Manufacturer nodes, LABELLED_BY edges.

    Each openFDA NDC entry is already keyed by product_ndc (one row per
    product, with package-size variants nested under `packaging`), so no
    separate package-level dedup is needed here.
    """
    for rec in records:
        drug_id = f"drug:{rec.product_ndc}"
        graph.add_node(
            drug_id,
            type="Drug",
            ndc_full=rec.product_ndc,
            brand_name=rec.brand_name,
            generic_name=rec.generic_name,
            dosage_form=rec.dosage_form,
            strength=", ".join(rec.active_ingredient_strengths),
            route=", ".join(rec.route),
            labeler_name=rec.labeler_name,
            application_no=rec.application_number,
            is_generic=rec.marketing_category == "ANDA",
            otc=rec.product_type == "HUMAN OTC DRUG",
            status=_drug_status(rec.listing_expiration_date),
            substance_name=rec.substance_name,
        )

        canonical = normalize_name(rec.labeler_name)
        mfr_id = _manufacturer_id(canonical)
        if not graph.has_node(mfr_id):
            graph.add_node(
                mfr_id,
                type="Manufacturer",
                canonical_name=canonical,
                raw_names=[rec.labeler_name],
                country="US",
                is_foreign=False,
                entity_type="manufacturer",
            )
        elif rec.labeler_name not in graph.nodes[mfr_id]["raw_names"]:
            graph.nodes[mfr_id]["raw_names"].append(rec.labeler_name)

        graph.add_edge(drug_id, mfr_id, key="LABELLED_BY")


def add_geography(graph: nx.MultiDiGraph, records: list[GeographyRecord]) -> None:
    for geo in records:
        graph.add_node(
            f"geo:{geo.state_code}",
            type="Geography",
            name=geo.name,
            centroid_lat=geo.centroid_lat,
            centroid_lng=geo.centroid_lng,
            region=geo.region,
        )


def add_distributors(graph: nx.MultiDiGraph, records: list[DistributorRecord]) -> None:
    """Pipeline step 5: DSCSA distributors -> Distributor nodes, LICENSED_IN edges."""
    for dist in records:
        dist_id = f"dist:{dist.license_number}"
        graph.add_node(
            dist_id,
            type="Distributor",
            name=dist.name,
            canonical_name=normalize_name(dist.name),
            distributor_type=dist.distributor_type,
            home_state=dist.home_state,
            city=dist.city,
            states_licensed=dist.states_licensed,
            national_coverage=dist.national_coverage,
        )
        for state in dist.states_licensed:
            geo_id = f"geo:{state}"
            if graph.has_node(geo_id):
                graph.add_edge(dist_id, geo_id, key="LICENSED_IN")


def build_graph(
    ndc_records: list[NdcRecord],
    distributor_records: list[DistributorRecord],
    geography_records: list[GeographyRecord],
) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    add_geography(graph, geography_records)
    add_ndc_records(graph, ndc_records)
    add_distributors(graph, distributor_records)
    return graph
