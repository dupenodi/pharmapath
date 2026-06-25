from collections import defaultdict
from datetime import date, datetime

import networkx as nx

from app.ingestion.models import (
    DistributorRecord,
    FacilityRecord,
    GeographyRecord,
    NdcRecord,
)
from app.ingestion.name_normalize import normalize_name
from app.ingestion.orange_book import OrangeBookEntry, ndc_application_key
from app.ingestion.repackagers import is_repackager

# Marketing categories that mean the product is a generic. ANDA is a standard
# generic; authorized generics are brand-owned but sold as generics.
_GENERIC_CATEGORIES = {"ANDA", "NDA AUTHORIZED GENERIC"}


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


def _ingredient_id(substance_name: str) -> str:
    return f"ingredient:{substance_name.strip().lower().replace(' ', '_')}"


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


def add_ndc_records(
    graph: nx.MultiDiGraph,
    records: list[NdcRecord],
    orange_book: dict[str, OrangeBookEntry] | None = None,
) -> None:
    """NDC -> Drug + Manufacturer + ActiveIngredient nodes.

    Edges: Drug-LABELLED_BY->Manufacturer, Drug-CONTAINS->ActiveIngredient.
    Drugs are enriched with Orange Book therapeutic-equivalence info where their
    FDA application number joins. Manufacturers get a heuristic repackager flag
    here; add_facilities() later overrides it authoritatively from DECRS.
    """
    orange_book = orange_book or {}
    for rec in records:
        drug_id = f"drug:{rec.product_ndc}"
        ob = orange_book.get(ndc_application_key(rec.application_number) or "")
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
            marketing_category=rec.marketing_category,
            is_generic=rec.marketing_category in _GENERIC_CATEGORIES,
            is_authorized_generic=rec.marketing_category == "NDA AUTHORIZED GENERIC",
            otc=rec.product_type == "HUMAN OTC DRUG",
            status=_drug_status(rec.listing_expiration_date),
            substance_name=rec.substance_name,
            in_orange_book=ob is not None,
            te_codes=sorted(ob.te_codes) if ob else [],
            te_groups=sorted(ob.te_groups) if ob else [],
        )

        canonical = normalize_name(rec.labeler_name)
        mfr_id = _manufacturer_id(canonical)
        repackager = is_repackager(rec.labeler_name, canonical)
        if not graph.has_node(mfr_id):
            graph.add_node(
                mfr_id,
                type="Manufacturer",
                canonical_name=canonical,
                raw_names=[rec.labeler_name],
                country="US",
                is_foreign=False,
                is_repackager=repackager,
                entity_type="repackager" if repackager else "manufacturer",
                repackager_source="heuristic",
            )
        elif rec.labeler_name not in graph.nodes[mfr_id]["raw_names"]:
            graph.nodes[mfr_id]["raw_names"].append(rec.labeler_name)
        graph.add_edge(drug_id, mfr_id, key="LABELLED_BY")

        for substance in rec.substance_name:
            if not substance:
                continue
            ing_id = _ingredient_id(substance)
            if not graph.has_node(ing_id):
                graph.add_node(ing_id, type="ActiveIngredient", name=substance.title())
            graph.add_edge(drug_id, ing_id, key="CONTAINS", is_active=True)


def add_facilities(graph: nx.MultiDiGraph, records: list[FacilityRecord]) -> None:
    """DECRS -> Facility nodes; OPERATES (Manufacturer->Facility) and
    LOCATED_IN (Facility->Geography) edges; authoritative repackager flag.

    Manufacturers are matched to facilities by canonical name (exact). A matched
    manufacturer's repackager status is set from its facilities' operations
    (DECRS is ground truth), overriding the NDC-name heuristic.
    """
    # Index existing Manufacturer nodes by canonical name for the join.
    mfr_by_canon: dict[str, list[str]] = defaultdict(list)
    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("type") == "Manufacturer":
            mfr_by_canon[attrs["canonical_name"]].append(node_id)

    # Collect, per matched manufacturer, whether any facility manufactures vs repacks.
    mfr_ops: dict[str, dict[str, bool]] = defaultdict(lambda: {"mfr": False, "repack": False})

    for fac in records:
        fac_id = f"facility:{fac.fei_number}" if fac.fei_number else f"facility:{fac.canonical_name}"
        graph.add_node(
            fac_id,
            type="Facility",
            fei_number=fac.fei_number,
            name=fac.firm_name,
            canonical_name=fac.canonical_name,
            city=fac.city,
            state=fac.state,
            country=fac.country,
            is_foreign=fac.is_foreign,
            operations=fac.operations,
            is_manufacturer=fac.is_manufacturer,
            is_repackager=fac.is_repackager,
            registrant_name=fac.registrant_name,
        )

        if not fac.is_foreign and fac.state:
            geo_id = f"geo:{fac.state}"
            if graph.has_node(geo_id):
                graph.add_edge(fac_id, geo_id, key="LOCATED_IN")

        for mfr_id in mfr_by_canon.get(fac.canonical_name, []):
            graph.add_edge(mfr_id, fac_id, key="OPERATES")
            # Touch the entry on every match, even if this facility's own ops are
            # neither manufacture nor repack/relabel (e.g. ANALYSIS-only) -- a
            # match at all is DECRS confirmation and must override the heuristic.
            ops = mfr_ops[mfr_id]
            if fac.is_manufacturer:
                ops["mfr"] = True
            if fac.is_repackager:
                ops["repack"] = True

    # Override the heuristic repackager flag with DECRS truth where we matched.
    for mfr_id, ops in mfr_ops.items():
        is_repack = ops["repack"] and not ops["mfr"]
        node = graph.nodes[mfr_id]
        node["is_repackager"] = is_repack
        node["entity_type"] = "repackager" if is_repack else "manufacturer"
        node["repackager_source"] = "decrs"


def add_distributors(graph: nx.MultiDiGraph, records: list[DistributorRecord]) -> None:
    """DSCSA distributors -> Distributor nodes, LICENSED_IN edges to Geography."""
    for dist in records:
        dist_id = f"dist:{dist.canonical_name.replace(' ', '_')}"
        graph.add_node(
            dist_id,
            type="Distributor",
            name=dist.name,
            canonical_name=dist.canonical_name,
            distributor_type=dist.distributor_type,
            home_state=dist.home_state,
            city=dist.city,
            states_licensed=dist.states_licensed,
            national_coverage=dist.national_coverage,
            license_count=dist.license_count,
        )
        for state in dist.states_licensed:
            geo_id = f"geo:{state}"
            if graph.has_node(geo_id):
                graph.add_edge(dist_id, geo_id, key="LICENSED_IN")


def build_graph(
    ndc_records: list[NdcRecord],
    distributor_records: list[DistributorRecord],
    geography_records: list[GeographyRecord],
    facility_records: list[FacilityRecord] | None = None,
    orange_book_index: dict[str, OrangeBookEntry] | None = None,
) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    add_geography(graph, geography_records)
    add_ndc_records(graph, ndc_records, orange_book_index)
    add_facilities(graph, facility_records or [])
    add_distributors(graph, distributor_records)
    return graph
