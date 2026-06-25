from app.ingestion.name_normalize import names_match, normalize_name


def test_strips_legal_suffixes():
    assert normalize_name("Amneal Pharmaceuticals LLC") == "amneal"
    assert normalize_name("AMNEAL PHARMS") == "amneal pharms"


def test_matches_known_variants():
    assert names_match("Amneal Pharmaceuticals LLC", "Amneal Pharmaceuticals")
    assert names_match("McKesson Corporation", "McKesson Corp")


def test_rejects_distinct_entities():
    assert not names_match("Teva Pharmaceuticals", "Teva UK Limited")


def test_dba_uses_trade_name():
    # The recognizable entity is the trade name after d/b/a, not the holding co.
    assert normalize_name("Denton Pharma, Inc. dba Northwind Pharmaceuticals") == "northwind"
    assert normalize_name("Heritage Pharma Labs Inc. d/b/a Avet Pharmaceuticals Inc") == "avet"
    assert names_match(
        "Denton Pharma, Inc. dba Northwind Pharmaceuticals",
        "Northwind Pharmaceuticals, Inc.",
    )


def test_never_collapses_to_empty():
    assert normalize_name("Pharmaceuticals LLC") != ""
