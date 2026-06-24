import json

from app.ingestion.fetch import download_to_raw, extract_zip_member
from app.ingestion.models import NdcRecord

NDC_BULK_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"


def fetch_ndc_json() -> dict:
    """Downloads (or reuses the cached copy of) the openFDA NDC bulk export."""
    zip_path = download_to_raw(NDC_BULK_URL, "ndc.json.zip")
    json_path = extract_zip_member(zip_path, ".json", zip_path.parent)
    with json_path.open() as f:
        return json.load(f)


def parse_ndc_records(raw: dict) -> list[NdcRecord]:
    records: list[NdcRecord] = []
    for entry in raw.get("results", []):
        strengths = [
            f"{a.get('strength', '')}".strip()
            for a in entry.get("active_ingredients", [])
            if a.get("strength")
        ]
        records.append(
            NdcRecord(
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
        )
    return records


def load_ndc_records() -> list[NdcRecord]:
    return parse_ndc_records(fetch_ndc_json())
