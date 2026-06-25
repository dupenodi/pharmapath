from app.ingestion.models import OrangeBookProduct
from app.ingestion.orange_book import (
    application_key,
    build_orange_book_index,
    ndc_application_key,
)


def test_application_key_strips_leading_zeros():
    assert application_key("A", "00211106") == "A211106"
    assert application_key("N", "021436") == "N21436"


def test_ndc_application_key_maps_prefixes():
    assert ndc_application_key("ANDA211106") == "A211106"
    assert ndc_application_key("NDA021436") == "N21436"
    assert ndc_application_key("BLA125085") == "B125085"
    assert ndc_application_key(None) is None
    assert ndc_application_key("UNAPPROVED") is None


def _ob(**kw) -> OrangeBookProduct:
    base = dict(
        ingredient="IBUPROFEN",
        df_route="TABLET;ORAL",
        trade_name="IBUPROFEN",
        applicant="X",
        strength="200MG",
        appl_type="A",
        appl_no="070001",
        product_no="001",
        te_code="AB",
        approval_date=None,
        type="RX",
        applicant_full_name="X",
    )
    base.update(kw)
    return OrangeBookProduct(**base)


def test_index_groups_te_codes_per_application():
    idx = build_orange_book_index([_ob(), _ob(strength="400MG", product_no="002")])
    entry = idx[application_key("A", "070001")]
    assert "AB" in entry.te_codes
    assert any("IBUPROFEN|TABLET;ORAL|AB" == g for g in entry.te_groups)
