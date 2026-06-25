from app.ingestion.repackagers import classify_entity, is_repackager


def test_known_repackagers_flagged():
    assert is_repackager("Bryant Ranch Prepack")
    assert is_repackager("A-S Medication Solutions")
    assert is_repackager("REMEDYREPACK INC.")


def test_heuristic_catches_repack_patterns():
    assert is_repackager("Some Unit Dose Services LLC")
    assert is_repackager("Acme Repackaging Co")
    assert is_repackager("Anytown Prepack Pharmacy")


def test_real_manufacturers_not_flagged():
    assert not is_repackager("Aurobindo Pharma Limited")
    assert not is_repackager("Hikma Pharmaceuticals USA Inc.")
    assert not is_repackager("Teva Pharmaceuticals USA, Inc.")


def test_classify_entity_labels():
    assert classify_entity("Bryant Ranch Prepack") == "repackager"
    assert classify_entity("Sun Pharmaceutical Industries, Inc.") == "manufacturer"
