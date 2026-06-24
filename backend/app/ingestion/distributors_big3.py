from app.ingestion.models import DistributorRecord

# Phase 1 scope: big-3 wholesale distributors only (see PLAN.md Assumption 1
# and the approved implementation plan). These are real, publicly known
# facts (headquarters city/state, national licensure) -- not a substitute
# for the actual DSCSA annual reporting database, which lists licenses by
# state and includes the ~6,000 other distributors deferred to Phase 8.
ALL_US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

BIG3_DISTRIBUTORS: list[DistributorRecord] = [
    DistributorRecord(
        license_number="BIG3-MCKESSON",
        name="McKesson Corporation",
        distributor_type="wholesale_distributor",
        home_state="TX",
        city="Irving",
        states_licensed=ALL_US_STATES,
        national_coverage=True,
    ),
    DistributorRecord(
        license_number="BIG3-CARDINAL",
        name="Cardinal Health, Inc.",
        distributor_type="wholesale_distributor",
        home_state="OH",
        city="Dublin",
        states_licensed=ALL_US_STATES,
        national_coverage=True,
    ),
    DistributorRecord(
        license_number="BIG3-CENCORA",
        name="Cencora, Inc. (formerly AmerisourceBergen)",
        distributor_type="wholesale_distributor",
        home_state="PA",
        city="Conshohocken",
        states_licensed=ALL_US_STATES,
        national_coverage=True,
    ),
]


def load_big3_distributors() -> list[DistributorRecord]:
    return list(BIG3_DISTRIBUTORS)
