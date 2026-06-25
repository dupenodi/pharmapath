"""Load the DECRS drug-establishment registration export (drls_reg.csv).

Gives us Facility nodes with operations (the authoritative manufacture vs
repack/relabel signal) and a location to link to Geography.
"""

import csv
from pathlib import Path

from app.core.config import settings
from app.ingestion.address import parse_address
from app.ingestion.models import FacilityRecord
from app.ingestion.name_normalize import normalize_name

csv.field_size_limit(10**7)

DECRS_FILENAME = "drls_reg.csv"

_MANUFACTURE_OPS = {"MANUFACTURE", "API MANUFACTURE"}
_REPACK_OPS = {"REPACK", "RELABEL"}


def decrs_file_path() -> Path:
    return settings.raw_data_dir / "decrs" / DECRS_FILENAME


def _parse_operations(raw: str) -> list[str]:
    return [op.strip() for op in (raw or "").split(";") if op.strip()]


def parse_decrs_file(path: Path) -> list[FacilityRecord]:
    records: list[FacilityRecord] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            firm = (row.get("FIRM_NAME") or "").strip()
            if not firm:
                continue
            ops = _parse_operations(row.get("OPERATIONS"))
            ops_set = set(ops)
            is_mfr = bool(ops_set & _MANUFACTURE_OPS)
            addr = parse_address(row.get("ADDRESS", ""))
            records.append(
                FacilityRecord(
                    fei_number=(row.get("FEI_NUMBER") or "").strip(),
                    firm_name=firm,
                    canonical_name=normalize_name(firm),
                    address=(row.get("ADDRESS") or "").strip(),
                    city=addr.city,
                    state=addr.state,
                    country=addr.country,
                    is_foreign=addr.is_foreign,
                    operations=ops,
                    is_manufacturer=is_mfr,
                    is_repackager=bool(ops_set & _REPACK_OPS) and not is_mfr,
                    expiration_date=(row.get("EXPIRATION_DATE") or "").strip() or None,
                    registrant_name=(row.get("REGISTRANT_NAME") or "").strip() or None,
                )
            )
    return records


def load_facility_records() -> list[FacilityRecord]:
    path = decrs_file_path()
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. See data/MANUAL_DOWNLOADS.md.")
    return parse_decrs_file(path)
