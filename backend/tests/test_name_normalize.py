from app.ingestion.name_normalize import names_match, normalize_name


def test_strips_legal_suffixes():
    assert normalize_name("Amneal Pharmaceuticals LLC") == "amneal"
    assert normalize_name("AMNEAL PHARMS") == "amneal pharms"


def test_matches_known_variants():
    assert names_match("Amneal Pharmaceuticals LLC", "Amneal Pharmaceuticals")
    assert names_match("McKesson Corporation", "McKesson Corp")


def test_rejects_distinct_entities():
    assert not names_match("Teva Pharmaceuticals", "Teva UK Limited")
