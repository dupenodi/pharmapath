import json
from pathlib import Path

from app.ingestion.models import NdcRecord
from app.ingestion.ndc import dedupe_ndc_records, parse_ndc_records

FIXTURE = Path(__file__).parent / "fixtures" / "ndc_sample.json"


def _rec(**kw) -> NdcRecord:
    base = dict(
        product_id="x",
        product_ndc="11111-111",
        generic_name="acetaminophen",
        brand_name=None,
        dosage_form="TABLET",
        route=["ORAL"],
        labeler_name="Acme",
        substance_name=["ACETAMINOPHEN"],
        application_number=None,
        product_type="HUMAN PRESCRIPTION DRUG",
        marketing_category="ANDA",
        finished=True,
        listing_expiration_date="20301231",
        active_ingredient_strengths=["500 mg/1"],
    )
    base.update(kw)
    return NdcRecord(**base)


def load_fixture() -> dict:
    with FIXTURE.open() as f:
        return json.load(f)


def test_parses_all_records():
    records = parse_ndc_records(load_fixture())
    assert len(records) == 2


def test_extracts_application_number_and_marketing_category():
    records = parse_ndc_records(load_fixture())
    rx_record = next(r for r in records if r.product_type == "HUMAN PRESCRIPTION DRUG")
    assert rx_record.application_number == "ANDA211106"
    assert rx_record.marketing_category == "ANDA"


def test_extracts_active_ingredient_strengths():
    records = parse_ndc_records(load_fixture())
    combo = next(r for r in records if len(r.substance_name) > 1)
    assert combo.substance_name == ["ACETAMINOPHEN", "BUTALBITAL", "CAFFEINE"]
    assert combo.active_ingredient_strengths == ["325 mg/1", "50 mg/1", "40 mg/1"]


def test_dedupe_keeps_one_per_ndc():
    records = [_rec(), _rec(brand_name="Tylenol")]
    deduped = dedupe_ndc_records(records)
    assert len(deduped) == 1


def test_dedupe_prefers_more_complete_record():
    sparse = _rec(brand_name=None, application_number=None)
    rich = _rec(brand_name="Tylenol", application_number="ANDA123")
    deduped = dedupe_ndc_records([sparse, rich])
    assert deduped[0].brand_name == "Tylenol"


def test_dedupe_prefers_active_listing():
    expired = _rec(listing_expiration_date=None, brand_name="Z", application_number="A1")
    active = _rec(listing_expiration_date="20301231")
    deduped = dedupe_ndc_records([expired, active])
    assert deduped[0].listing_expiration_date == "20301231"
