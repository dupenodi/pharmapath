from app.ingestion.distributors import parse_dscsa_dir

HEADER = (
    "Facility Name,Facility Type,License Number,License State,License Expire,"
    "Reporting Year,Address,Facility Contact Name,Facility Contact Email"
)


def _state_file(directory, state, *rows):
    (directory / f"{state}.csv").write_text(HEADER + "\n" + "\n".join(rows) + "\n")


def test_aggregates_entity_across_states(tmp_path):
    _state_file(
        tmp_path,
        "CA",
        '"Acme Distribution, Inc. DBA: Acme Rx",WDD,111,US-CA,06/30/2026,2026,addr,c,e',
    )
    _state_file(
        tmp_path,
        "NV",
        '"Acme Distribution, Inc. DBA: Acme Rx",WDD,222,US-NV,06/30/2026,2026,addr,c,e',
    )
    records = parse_dscsa_dir(tmp_path)
    assert len(records) == 1
    rec = records[0]
    assert set(rec.states_licensed) == {"CA", "NV"}
    assert rec.distributor_type == "wholesale_distributor"
    assert rec.license_count == 2


def test_3pl_type_and_dba_na(tmp_path):
    _state_file(
        tmp_path,
        "TX",
        '"Logistics Co DBA: N/A",3PL,999,US-TX,06/30/2026,2026,addr,c,e',
    )
    records = parse_dscsa_dir(tmp_path)
    assert records[0].distributor_type == "third_party_logistics"
    # "DBA: N/A" must not become part of the canonical name.
    assert "n a" not in records[0].canonical_name
