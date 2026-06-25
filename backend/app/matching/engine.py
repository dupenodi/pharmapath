import asyncio

import networkx as nx
from haversine import haversine

from app.graph.live_enrich import enrich_drug_with_shortage, enrich_manufacturer_with_compliance
from app.graph.queries import find_alternatives as find_te_alternatives
from app.matching.models import AlternativeDrug, MatchResult, ProcurementRequest, RiskSummary, SupplierMatch
from app.matching.scoring import score_candidate
from app.services.openfda import fetch_enforcement
from app.services.openfda_models import Shortage

NATIONAL_COVERAGE_QUANTITY_THRESHOLD = 50_000
MAX_RETURNED_MATCHES = 25

# Bounds how many live openFDA compliance checks run at once. A populous
# state can have 300-500+ candidate distributors (national-coverage carriers
# qualify everywhere) -- awaiting fetch_enforcement for each one sequentially
# turned a single query into minutes of wall-clock time. Unbounded
# concurrency would fix the latency but risks tripping openFDA's per-IP rate
# limit; a semaphore caps concurrency without serializing everything.
LIVE_LOOKUP_CONCURRENCY = 20


def _state_distance_km(graph: nx.MultiDiGraph, state_a: str, state_b: str) -> float | None:
    geo_a, geo_b = graph.nodes.get(f"geo:{state_a}"), graph.nodes.get(f"geo:{state_b}")
    if geo_a is None or geo_b is None:
        return None
    return haversine((geo_a["centroid_lat"], geo_a["centroid_lng"]), (geo_b["centroid_lat"], geo_b["centroid_lng"]))


def _manufacturer_distance_km(graph: nx.MultiDiGraph, mfr_id: str, delivery_state: str) -> float | None:
    """Closest of a manufacturer's DECRS-linked facilities to the delivery state.

    Only ~1/3 of manufacturers have a facility link (DECRS doesn't cover every
    NDC labeler), so this still returns None for the rest -- callers must keep
    treating None as "unknown", not "far away".
    """
    best: float | None = None
    for facility_id in graph.successors(mfr_id):
        facility = graph.nodes[facility_id]
        if facility.get("type") != "Facility" or not facility.get("state"):
            continue
        distance = _state_distance_km(graph, facility["state"], delivery_state)
        if distance is not None and (best is None or distance < best):
            best = distance
    return best


def _distributor_candidates(graph: nx.MultiDiGraph, request: ProcurementRequest) -> list[str]:
    """Distributors worth a live compliance check for this request.

    score_candidate hard-disqualifies anyone not licensed in the delivery
    state (unless they have national coverage), so screening on that first --
    before the live openFDA call -- avoids firing one HTTP request per
    distributor in the graph (1,356 of them) when at most a few dozen could
    ever pass.
    """
    state = request.delivery_state
    return [
        n
        for n, d in graph.nodes(data=True)
        if d.get("type") == "Distributor"
        and (d.get("national_coverage") or graph.has_edge(n, f"geo:{state}", key="LICENSED_IN"))
    ]


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

    # Manufacturers aren't licensed by state like distributors, so state
    # licensing never disqualifies one. Distance comes from its DECRS-linked
    # facilities when available (~1/3 of manufacturers); otherwise unknown,
    # which scoring treats as mid-range and flags via a caveat.
    distance_km = _manufacturer_distance_km(graph, mfr_id, request.delivery_state)
    result = score_candidate(
        candidate_name=mfr["canonical_name"],
        flags=flags,
        shortage=shortage,
        distance_km=distance_km,
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
        distance_km=distance_km,
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

    semaphore = asyncio.Semaphore(LIVE_LOOKUP_CONCURRENCY)

    async def score_distributor_bounded(dist_id: str) -> SupplierMatch | None:
        async with semaphore:
            return await _score_distributor(graph, dist_id, request, shortage)

    async def score_manufacturer_bounded(mfr_id: str) -> SupplierMatch | None:
        async with semaphore:
            return await _score_manufacturer(graph, mfr_id, request, shortage)

    results = await asyncio.gather(
        *(score_distributor_bounded(d) for d in _distributor_candidates(graph, request)),
        *(score_manufacturer_bounded(m) for m in _manufacturer_candidates(graph, drug_id)),
    )
    matches: list[SupplierMatch] = [m for m in results if m is not None]

    matches.sort(key=lambda m: m.score, reverse=True)
    matches_total = len(matches)
    risk_summary = _risk_summary(matches, shortage)  # on the full set, before any display cap
    matches = matches[:MAX_RETURNED_MATCHES]

    if not matches:
        explanation = (
            f"No licensed distributors found in {request.delivery_state}, and no manufacturer "
            "candidates passed compliance screening."
        )
    elif matches_total > MAX_RETURNED_MATCHES:
        explanation = (
            f"Found {matches_total} candidate supplier(s) for delivery to {request.delivery_state} -- "
            f"showing the top {MAX_RETURNED_MATCHES} by score."
        )
    else:
        explanation = f"Found {matches_total} candidate supplier(s) for delivery to {request.delivery_state}."

    # Surface therapeutic equivalents whenever they'd actually matter: an
    # active shortage, or no suppliers cleared screening at all.
    alternatives: list[AlternativeDrug] = []
    if shortage is not None and shortage.status == "active" or not matches:
        te = find_te_alternatives(graph, drug_id)
        alternatives = [
            AlternativeDrug(
                drug_id=item["id"],
                generic_name=item["label"],
                brand_name=graph.nodes[item["id"]].get("brand_name"),
                relationship="therapeutic",
            )
            for item in te["items"]
        ]

    return MatchResult(
        resolved_drug_id=drug_id,
        matches=matches,
        alternatives=alternatives,
        risk_summary=risk_summary,
        explanation=explanation,
        matches_total=matches_total,
    )
