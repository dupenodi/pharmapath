"""Load licensed wholesale distributors / 3PLs from the DSCSA per-state exports.

Each of the 52 `dscsa/<STATE>.csv` files lists the distributors licensed in
that state (one row per license). The same company appears in many states, so
we aggregate rows into one entity per company and collect the states it covers.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

from app.core.config import settings
from app.ingestion.models import DistributorRecord
from app.ingestion.name_normalize import normalize_name

csv.field_size_limit(10**7)

# Coverage at/above this many states is treated as effectively national.
_NATIONAL_THRESHOLD = 40
_DBA = re.compile(r"\s+d/?b/?a:?\s+", re.IGNORECASE)


def dscsa_dir() -> Path:
    return settings.raw_data_dir / "dscsa"


def _legal_name(facility_name: str) -> str:
    """Use the legal name (left of "DBA:"); fall back to the whole string."""
    parts = _DBA.split(facility_name, maxsplit=1)
    legal = parts[0].strip()
    return legal or facility_name.strip()


_TYPE_MAP = {"WDD": "wholesale_distributor", "3PL": "third_party_logistics"}


def parse_dscsa_dir(directory: Path) -> list[DistributorRecord]:
    agg: dict[str, dict] = defaultdict(
        lambda: {
            "names": [],
            "states": set(),
            "types": set(),
            "licenses": [],
            "home_states": [],
        }
    )
    for csv_path in sorted(directory.glob("*.csv")):
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                raw_name = (row.get("Facility Name") or "").strip()
                if not raw_name:
                    continue
                legal = _legal_name(raw_name)
                key = normalize_name(legal)
                if not key:
                    continue
                entry = agg[key]
                entry["names"].append(legal)
                state = (row.get("License State") or "").replace("US-", "").strip()
                if state:
                    entry["states"].add(state)
                    entry["home_states"].append(state)
                ftype = (row.get("Facility Type") or "").strip().upper()
                if ftype:
                    entry["types"].add(ftype)
                lic = (row.get("License Number") or "").strip()
                if lic:
                    entry["licenses"].append(lic)

    records: list[DistributorRecord] = []
    for key, e in agg.items():
        states = sorted(e["states"])
        # A company can be both WDD and 3PL; prefer wholesale_distributor label.
        dtype = "wholesale_distributor" if "WDD" in e["types"] else (
            _TYPE_MAP.get(next(iter(e["types"]), ""), "wholesale_distributor")
        )
        home_state = max(set(e["home_states"]), key=e["home_states"].count) if e["home_states"] else ""
        records.append(
            DistributorRecord(
                license_number=e["licenses"][0] if e["licenses"] else key,
                name=max(e["names"], key=len),  # most descriptive spelling
                canonical_name=key,
                distributor_type=dtype,
                home_state=home_state,
                city="",
                states_licensed=states,
                national_coverage=len(states) >= _NATIONAL_THRESHOLD,
                license_count=len(e["licenses"]),
            )
        )
    return records


def load_distributor_records() -> list[DistributorRecord]:
    directory = dscsa_dir()
    if not directory.exists():
        raise FileNotFoundError(f"{directory} not found. See data/MANUAL_DOWNLOADS.md.")
    return parse_dscsa_dir(directory)
