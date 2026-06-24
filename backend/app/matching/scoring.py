from dataclasses import dataclass

from app.services.openfda_models import ComplianceFlag, Shortage


@dataclass
class ScoreResult:
    score: float
    breakdown: dict
    compliance_status: str  # "clean" | "flagged" | "unknown"
    shortage_risk: str  # "none" | "possible" | "confirmed"
    caveats: list[str]


def _compliance_score(flags: list[ComplianceFlag] | None) -> tuple[float, str]:
    if flags is None:
        return 1.0, "unknown"  # never assume clean -- caller adds the caveat
    active = [f for f in flags if f.status == "active"]
    if any(f.severity == "critical" for f in active):
        return 0.0, "flagged"
    if any(f.severity == "high" for f in active):
        return 0.3, "flagged"
    if any(f.severity == "medium" for f in active):
        return 0.7, "flagged"
    return 1.0, "clean"


def _availability_score(shortage: Shortage | None, candidate_name: str) -> tuple[float, str]:
    if shortage is None:
        return 1.0, "none"
    if any(candidate_name.lower() in firm.lower() for firm in shortage.affected_firms):
        return 0.0, "confirmed"
    return 0.5, "possible"


def _location_score(distance_km: float | None) -> float:
    if distance_km is None:
        return 0.4  # facility/distance data unavailable -- treated as mid-range, flagged via caveat
    if distance_km < 500:
        return 1.0
    if distance_km < 1500:
        return 0.7
    if distance_km < 3000:
        return 0.4
    return 0.2


def _coverage_score(licensed_in_state: bool, national_coverage: bool) -> float:
    if licensed_in_state:
        return 1.0
    if national_coverage:
        return 0.8
    return 0.0


def score_candidate(
    *,
    candidate_name: str,
    flags: list[ComplianceFlag] | None,
    shortage: Shortage | None,
    distance_km: float | None,
    licensed_in_state: bool,
    national_coverage: bool,
    deadline_days: int | None = None,
    is_repackager: bool = False,
) -> ScoreResult | None:
    """Implements PLAN.md's score_candidate exactly: 4 weighted dimensions,
    hard disqualifiers, and the urgency modifier for deadline_days < 7."""
    compliance_score, compliance_status = _compliance_score(flags)
    availability_score, shortage_risk = _availability_score(shortage, candidate_name)
    location_score = _location_score(distance_km)
    coverage_score = _coverage_score(licensed_in_state, national_coverage)

    if coverage_score == 0.0:
        return None  # not licensed in the delivery state
    if compliance_score == 0.0:
        return None  # Class I recall -- excluded

    if deadline_days is not None and deadline_days < 7:
        weights = {"compliance": 0.40, "availability": 0.20, "location": 0.35, "coverage": 0.05}
    else:
        weights = {"compliance": 0.40, "availability": 0.25, "location": 0.25, "coverage": 0.10}

    score = (
        compliance_score * weights["compliance"]
        + availability_score * weights["availability"]
        + location_score * weights["location"]
        + coverage_score * weights["coverage"]
    )

    caveats: list[str] = []
    if flags is None:
        caveats.append("Compliance data unavailable -- not assumed clean.")
    if distance_km is None:
        caveats.append("Facility location data unavailable -- distance to delivery location unknown.")
    if is_repackager:
        score -= 0.1
        caveats.append("This supplier is a repackager, not the original manufacturer. Original manufacturer's compliance status may differ.")

    return ScoreResult(
        score=round(score, 3),
        breakdown={
            "compliance": compliance_score,
            "availability": availability_score,
            "location": location_score,
            "coverage": coverage_score,
        },
        compliance_status=compliance_status,
        shortage_risk=shortage_risk,
        caveats=caveats,
    )
