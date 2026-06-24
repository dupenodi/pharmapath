import json
from pathlib import Path

from app.ingestion.ndc import parse_ndc_records

FIXTURE = Path(__file__).parent / "fixtures" / "ndc_sample.json"


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
