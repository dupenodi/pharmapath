from datetime import date

from app.matching.scoring import score_candidate
from app.services.openfda_models import ComplianceFlag, Shortage


def make_flag(severity: str, status: str = "active") -> ComplianceFlag:
    return ComplianceFlag(
        id=f"flag-{severity}",
        flag_type="recall",
        severity=severity,
        status=status,
        issued_date="20260101",
        closed_date=None,
        description="test",
        source_url=None,
        affected_products=[],
    )


def make_shortage(affected_firms: list[str]) -> Shortage:
    return Shortage(
        id="shortage-1",
        drug_name="Test Drug",
        generic_name="Test",
        status="active",
        reason="test",
        start_date="20260101",
        resolved_date=None,
        affected_firms=affected_firms,
        last_checked=date.today(),
    )


def test_clean_candidate_close_and_licensed_scores_high():
    result = score_candidate(
        candidate_name="Cardinal Health",
        flags=[],
        shortage=None,
        distance_km=100,
        licensed_in_state=True,
        national_coverage=True,
    )
    assert result is not None
    assert result.compliance_status == "clean"
    assert result.score > 0.9


def test_class_i_recall_disqualifies_candidate():
    result = score_candidate(
        candidate_name="Bad Manufacturer",
        flags=[make_flag("critical")],
        shortage=None,
        distance_km=100,
        licensed_in_state=True,
        national_coverage=False,
    )
    assert result is None


def test_not_licensed_and_not_national_disqualifies_candidate():
    result = score_candidate(
        candidate_name="Regional Co",
        flags=[],
        shortage=None,
        distance_km=100,
        licensed_in_state=False,
        national_coverage=False,
    )
    assert result is None


def test_unknown_compliance_never_assumed_clean():
    result = score_candidate(
        candidate_name="Unknown Co",
        flags=None,
        shortage=None,
        distance_km=100,
        licensed_in_state=True,
        national_coverage=False,
    )
    assert result is not None
    assert result.compliance_status == "unknown"
    assert any("Compliance data unavailable" in c for c in result.caveats)


def test_shortage_with_named_firm_zeroes_availability():
    result = score_candidate(
        candidate_name="Walgreens",
        flags=[],
        shortage=make_shortage(["Walgreens"]),
        distance_km=100,
        licensed_in_state=True,
        national_coverage=False,
    )
    assert result is not None
    assert result.shortage_risk == "confirmed"
    assert result.breakdown["availability"] == 0.0


def test_shortage_without_named_firm_is_possible_risk():
    result = score_candidate(
        candidate_name="McKesson",
        flags=[],
        shortage=make_shortage(["Some Other Firm"]),
        distance_km=100,
        licensed_in_state=True,
        national_coverage=True,
    )
    assert result is not None
    assert result.shortage_risk == "possible"
    assert result.breakdown["availability"] == 0.5


def test_unknown_distance_flags_caveat_and_mid_score():
    result = score_candidate(
        candidate_name="Some Manufacturer",
        flags=[],
        shortage=None,
        distance_km=None,
        licensed_in_state=True,
        national_coverage=False,
    )
    assert result is not None
    assert result.breakdown["location"] == 0.4
    assert any("Facility location data unavailable" in c for c in result.caveats)


def test_repackager_downgraded_with_caveat():
    base = score_candidate(
        candidate_name="Repacker Co",
        flags=[],
        shortage=None,
        distance_km=100,
        licensed_in_state=True,
        national_coverage=False,
        is_repackager=False,
    )
    repackaged = score_candidate(
        candidate_name="Repacker Co",
        flags=[],
        shortage=None,
        distance_km=100,
        licensed_in_state=True,
        national_coverage=False,
        is_repackager=True,
    )
    assert repackaged.score == round(base.score - 0.1, 3)
    assert any("repackager" in c.lower() for c in repackaged.caveats)


def test_urgency_modifier_weights_location_more_under_deadline():
    near_deadline = score_candidate(
        candidate_name="Far Co",
        flags=[],
        shortage=None,
        distance_km=4000,
        licensed_in_state=True,
        national_coverage=True,
        deadline_days=3,
    )
    no_deadline = score_candidate(
        candidate_name="Far Co",
        flags=[],
        shortage=None,
        distance_km=4000,
        licensed_in_state=True,
        national_coverage=True,
        deadline_days=None,
    )
    # location_score is 0.2 either way (>3000km); urgency weights it at 0.35 vs 0.25,
    # so the urgent score should be lower since the far-away location score drags more.
    assert near_deadline.score < no_deadline.score
