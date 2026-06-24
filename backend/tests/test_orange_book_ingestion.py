from pathlib import Path

from app.ingestion.orange_book import parse_products_file

FIXTURE = Path(__file__).parent / "fixtures" / "orange_book_products.txt"


def test_parses_all_rows():
    products = parse_products_file(FIXTURE)
    assert len(products) == 2


def test_parses_te_code_and_blank_te_code_as_none():
    products = parse_products_file(FIXTURE)
    rx = next(p for p in products if p.type == "RX")
    otc = next(p for p in products if p.type == "OTC")
    assert rx.te_code == "AB"
    assert otc.te_code is None


def test_parses_known_fields():
    products = parse_products_file(FIXTURE)
    rx = next(p for p in products if p.type == "RX")
    assert rx.ingredient == "ACETAMINOPHEN"
    assert rx.appl_no == "ANDA040458"
    assert rx.strength == "500MG"
