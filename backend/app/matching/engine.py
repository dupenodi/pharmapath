import networkx as nx
from haversine import haversine

from app.graph.live_enrich import enrich_drug_with_shortage, enrich_manufacturer_with_compliance
from app.matching.models import MatchResult, ProcurementRequest, RiskSummary, SupplierMatch
from app.matching.scoring import score_candidate
from app.services.openfda import fetch_enforcement
from app.services.openfda_models import Shortage

NATIONAL_COVERAGE_QUANTITY_THRESHOLD = 50_000


def _state_distance_km(graph: nx.MultiDiGraph, state_a: str, state_b: str) -> float | None:
    geo_a, geo_b = graph.nodes.get(f"geo:{state_a}"), graph.nodes.get(f"geo:{state_b}")
    if geo_a is None or geo_b is None:
        return None
    return haversine((geo_a["centroid_lat"], geo_a["centroid_lng"]), (geo_b["centroid_lat"], geo_b["centroid_lng"]))


def _distributor_candidates(graph: nx.MultiDiGraph) -> list[str]:
    return [n for n, d in graph.nodes(data=True) if d.get("type") == "Distributor"]


def _manufacturer_candidates(graph: nx.MultiDiGraph, drug_id: str) -> list[str]:
    return [n for n in graph.successors(drug_id) if graph.nodes[n].get("type") == "Manufacturer"]


async def _score_distributor(
    graph: nx.MultiDiGraph, dist_id: str, request: ProcurementRequest, shortage: Shortage | None
) -> SupplierMatch | None:
    dist = graph.nodes[dist_id]
    licensed_in_state = graph.has_edge(dist_id, f"geo:{request.delivery_state}", key="LICENSED_IN")
    distance_km = _state_distance_km(graph, dist["home_state"], request.delivery_state)

    flags = await fetch_enforcement(dist["name"])
    result = score_candidate(
        candidate_name=dist["name"],
        flags=flags,
        shortage=shortage,
        distance_km=distance_km,
        licensed_in_state=licensed_in_state,
        national_coverage=dist["national_coverage"],
        deadline_days=request.deadline_days,
    )
    if result is None:
        return None

    caveats = list(result.caveats) + ["Stock availability not confirmed -- distributor licensing data only."]
    if request.quantity and request.quantity > NATIONAL_COVERAGE_QUANTITY_THRESHOLD and not dist["national_coverage"]:
        return None
    if request.quantity and request.quantity > NATIONAL_COVERAGE_QUANTITY_THRESHOLD:
        caveats.append("For orders of this size, recommend contacting national distributors directly to confirm stock.")

    return SupplierMatch(
        supplier_id=dist_id,
        supplier_name=dist["name"],
        supplier_type="distributor",
        score=result.score,
        compliance_status=result.compliance_status,
        active_flags=[f.model_dump() for f in flags] if flags else [],
        licensed_in_state=licensed_in_state,
        states_licensed=dist["states_licensed"],
        shortage_risk=result.shortage_risk,
        distance_km=distance_km,
        score_breakdown=result.breakdown,
        caveats=caveats,
    )


async def _score_manufacturer(
    graph: nx.MultiDiGraph, mfr_id: str, request: ProcurementRequest, shortage: Shortage | None
) -> SupplierMatch | None:
    mfr = graph.nodes[mfr_id]
    flags = await enrich_manufacturer_with_compliance(graph, mfr_id)
    is_repackager = mfr.get("entity_type") == "repackager"

    # No Facility/DECRS data yet (see data/MANUAL_DOWNLOADS.md) -- distance and
    # state licensing for direct manufacturers can't be determined. Treat as
    # not state-disqualifying (manufacturers aren't licensed by state like
    # distributors) but flag the unknown distance via scoring's caveat.
    result = score_candidate(
        candidate_name=mfr["canonical_name"],
        flags=flags,
        shortage=shortage,
        distance_km=None,
        licensed_in_state=True,
        national_coverage=False,
        deadline_days=request.deadline_days,
        is_repackager=is_repackager,
    )
    if result is None:
        return None

    return SupplierMatch(
        supplier_id=mfr_id,
        supplier_name=mfr["raw_names"][0] if mfr.get("raw_names") else mfr["canonical_name"],
        supplier_type="manufacturer_direct",
        score=result.score,
        compliance_status=result.compliance_status,
        active_flags=[f.model_dump() for f in flags] if flags else [],
        licensed_in_state=True,
        states_licensed=[],
        shortage_risk=result.shortage_risk,
        distance_km=None,
        score_breakdown=result.breakdown,
        caveats=result.caveats + ["Manufacturers rarely sell direct to hospitals; treat as a lower-priority fallback."],
    )


def _risk_summary(matches: list[SupplierMatch], shortage: Shortage | None) -> RiskSummary:
    manufacturers_total = sum(1 for m in matches if m.supplier_type == "manufacturer_direct")
    manufacturers_flagged = sum(1 for m in matches if m.supplier_type == "manufacturer_direct" and m.compliance_status == "flagged")
    shortage_active = shortage is not None and shortage.status == "active"

    risk_flags = []
    if shortage_active:
        risk_flags.append(f"Active shortage: {shortage.reason or 'reason not specified'}.")
    if manufacturers_flagged:
        risk_flags.append(f"{manufacturers_flagged} of {manufacturers_total} manufacturers have active compliance flags.")

    if shortage_active and manufacturers_flagged:
        overall = "critical"
    elif shortage_active or manufacturers_flagged:
        overall = "high" if (manufacturers_total and manufacturers_flagged == manufacturers_total) else "medium"
    else:
        overall = "low"

    return RiskSummary(
        overall_risk=overall,
        shortage_active=shortage_active,
        manufacturers_flagged=manufacturers_flagged,
        manufacturers_total=manufacturers_total,
        risk_flags=risk_flags,
    )


async def match_suppliers(graph: nx.MultiDiGraph, drug_id: str, request: ProcurementRequest) -> MatchResult:
    if not request.delivery_state:
        return MatchResult(
            resolved_drug_id=drug_id,
            matches=[],
            alternatives=[],
            risk_summary=None,
            explanation="Please specify the delivery state to run supplier matching.",
        )

    if not graph.has_node(drug_id):
        return MatchResult(resolved_drug_id=None, matches=[], alternatives=[], risk_summary=None, explanation=f"Drug {drug_id!r} not found.")

    shortages = await enrich_drug_with_shortage(graph, drug_id)
    shortage = next((s for s in shortages if s.status == "active"), shortages[0] if shortages else None)

    matches: list[SupplierMatch] = []
    for dist_id in _distributor_candidates(graph):
        match = await _score_distributor(graph, dist_id, request, shortage)
        if match is not None:
            matches.append(match)

    for mfr_id in _manufacturer_candidates(graph, drug_id):
        match = await _score_manufacturer(graph, mfr_id, request, shortage)
        if match is not None:
            matches.append(match)

    matches.sort(key=lambda m: m.score, reverse=True)

    if not matches:
        explanation = (
            f"No licensed distributors found in {request.delivery_state}, and no manufacturer "
            "candidates passed compliance screening."
        )
    else:
        explanation = f"Found {len(matches)} candidate supplier(s) for delivery to {request.delivery_state}."

    return MatchResult(
        resolved_drug_id=drug_id,
        matches=matches,
        alternatives=[],  # EQUIVALENT_TO not populated until Orange Book data is ingested
        risk_summary=_risk_summary(matches, shortage),
        explanation=explanation,
    )
