from app.ingestion.decrs import parse_decrs_file

HEADER = (
    "FEI_NUMBER,DUNS_NUMBER,FIRM_NAME,ADDRESS,EXPIRATION_DATE,OPERATIONS,"
    "ESTABLISHMENT_CONTACT_NAME,ESTABLISHMENT_CONTACT_EMAIL,AGENT_DETAILS,"
    "REGISTRANT_NAME,REGISTRANT_DUNS,REGISTRANT_CONTACT_NAME,REGISTRANT_CONTACT_EMAIL,EXCLUSION_FLAG"
)


def _write(tmp_path, *rows):
    p = tmp_path / "drls_reg.csv"
    p.write_text(HEADER + "\n" + "\n".join(rows) + "\n")
    return p


def test_classifies_manufacturer_vs_repackager(tmp_path):
    rows = [
        '111,1,Acme Pharma Inc,"1 Main St, Newark, New Jersey (NJ) 07101, United States (USA)",'
        '12/31/2026,MANUFACTURE; ANALYSIS,,,,,Acme,,,N',
        '222,2,Repackit LLC,"2 Oak St, Reno, Nevada (NV) 89501, United States (USA)",'
        '12/31/2026,REPACK; RELABEL,,,,,Repackit,,,N',
    ]
    facs = parse_decrs_file(_write(tmp_path, *rows))
    by_name = {f.firm_name: f for f in facs}
    assert by_name["Acme Pharma Inc"].is_manufacturer is True
    assert by_name["Acme Pharma Inc"].is_repackager is False
    assert by_name["Acme Pharma Inc"].state == "NJ"
    assert by_name["Repackit LLC"].is_repackager is True
    assert by_name["Repackit LLC"].is_manufacturer is False


def test_foreign_facility_flagged(tmp_path):
    rows = [
        '333,3,Global API Ltd,"Plot 5, Gujarat 393002, India (IND)",12/31/2026,API MANUFACTURE,,,,,Global,,,N'
    ]
    facs = parse_decrs_file(_write(tmp_path, *rows))
    assert facs[0].is_foreign is True
    assert facs[0].is_manufacturer is True
    assert facs[0].state == ""
