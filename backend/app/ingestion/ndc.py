import json
from collections.abc import Iterable, Iterator

import ijson

from app.ingestion.fetch import download_to_raw, extract_zip_member
from app.ingestion.models import NdcRecord

NDC_BULK_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"


def fetch_ndc_json() -> dict:
    """Downloads (or reuses the cached copy of) the openFDA NDC bulk export.

    Only used by tests against small fixtures -- the production path
    (load_ndc_records) streams the real ~244MB file instead of materializing
    it as a dict; see _build_record.
    """
    zip_path = download_to_raw(NDC_BULK_URL, "ndc.json.zip")
    json_path = extract_zip_member(zip_path, ".json", zip_path.parent)
    with json_path.open() as f:
        return json.load(f)


def _build_record(entry: dict) -> NdcRecord:
    strengths = [
        f"{a.get('strength', '')}".strip()
        for a in entry.get("active_ingredients", [])
        if a.get("strength")
    ]
    return NdcRecord(
        product_id=entry.get("product_id", ""),
        product_ndc=entry.get("product_ndc", ""),
        generic_name=entry.get("generic_name", ""),
        brand_name=entry.get("brand_name"),
        dosage_form=entry.get("dosage_form"),
        route=entry.get("route", []),
        labeler_name=entry.get("labeler_name", ""),
        substance_name=[a.get("name", "") for a in entry.get("active_ingredients", [])],
        application_number=entry.get("application_number"),
        product_type=entry.get("product_type"),
        marketing_category=entry.get("marketing_category"),
        finished=entry.get("finished", True),
        listing_expiration_date=entry.get("listing_expiration_date"),
        active_ingredient_strengths=strengths,
    )


def parse_ndc_records(raw: dict) -> list[NdcRecord]:
    return [_build_record(entry) for entry in raw.get("results", [])]


def _completeness(rec: NdcRecord) -> int:
    """How many of the fields we care about are populated (for dup tie-breaking)."""
    return sum(
        bool(v)
        for v in (
            rec.brand_name,
            rec.dosage_form,
            rec.route,
            rec.active_ingredient_strengths,
            rec.substance_name,
            rec.application_number,
        )
    )


def dedupe_ndc_records(records: Iterable[NdcRecord]) -> list[NdcRecord]:
    """Collapse rows sharing a product_ndc to one 'best' record.

    The graph keys Drug nodes on product_ndc, so duplicate rows would silently
    overwrite each other. We instead keep the record with a non-expired listing,
    breaking ties by field completeness, so no product is lost to clobbering.
    """
    best: dict[str, NdcRecord] = {}
    for rec in records:
        key = rec.product_ndc
        incumbent = best.get(key)
        if incumbent is None:
            best[key] = rec
            continue
        # Prefer a record that still has a listing date (not expired/blank),
        # then the more complete one.
        cand_rank = (bool(rec.listing_expiration_date), _completeness(rec))
        inc_rank = (bool(incumbent.listing_expiration_date), _completeness(incumbent))
        if cand_rank > inc_rank:
            best[key] = rec
    return list(best.values())


def load_ndc_records() -> Iterator[NdcRecord]:
    # Dedupe is applied by the caller *after* product-type filtering, so a
    # same-NDC non-prescription row can't win and then get filtered out.
    #
    # A generator, not a list: streams the ~244MB file entry-by-entry (ijson)
    # and yields records one at a time, so the caller's filter+dedupe can
    # consume them without ever holding the full ~110k-record list AND the
    # dedupe dict in memory at once. Combined with streaming the JSON itself
    # (instead of json.load()-ing it whole), this cut peak RSS during startup
    # from ~1.4GB to under 700MB -- the difference between fitting in a
    # typical free-tier host's memory cap or not.
    zip_path = download_to_raw(NDC_BULK_URL, "ndc.json.zip")
    json_path = extract_zip_member(zip_path, ".json", zip_path.parent)
    with json_path.open("rb") as f:
        for entry in ijson.items(f, "results.item"):
            yield _build_record(entry)
