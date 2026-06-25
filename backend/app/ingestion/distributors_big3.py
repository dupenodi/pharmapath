from app.ingestion.models import DistributorRecord

# Big-3 wholesale distributors as a small, deterministic fixture for tests.
# Production seeding now uses the real DSCSA per-state exports
# (app.ingestion.distributors.load_distributor_records); this stub is retained
# only so unit tests don't need the full 1,300+ distributor dataset.
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
        canonical_name="mckesson",
        distributor_type="wholesale_distributor",
        home_state="TX",
        city="Irving",
        states_licensed=ALL_US_STATES,
        national_coverage=True,
        license_count=len(ALL_US_STATES),
    ),
    DistributorRecord(
        license_number="BIG3-CARDINAL",
        name="Cardinal Health, Inc.",
        canonical_name="cardinal health",
        distributor_type="wholesale_distributor",
        home_state="OH",
        city="Dublin",
        states_licensed=ALL_US_STATES,
        national_coverage=True,
        license_count=len(ALL_US_STATES),
    ),
    DistributorRecord(
        license_number="BIG3-CENCORA",
        name="Cencora, Inc. (formerly AmerisourceBergen)",
        canonical_name="cencora",
        distributor_type="wholesale_distributor",
        home_state="PA",
        city="Conshohocken",
        states_licensed=ALL_US_STATES,
        national_coverage=True,
        license_count=len(ALL_US_STATES),
    ),
]


def load_big3_distributors() -> list[DistributorRecord]:
    return list(BIG3_DISTRIBUTORS)
