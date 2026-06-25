from app.ingestion.address import parse_address


def test_domestic_address():
    p = parse_address("3350 North Ridge Avenue, Arlington Heights, Illinois (IL) 60004, United States (USA)")
    assert p.country == "USA"
    assert p.is_foreign is False
    assert p.state == "IL"
    assert p.city == "Arlington Heights"


def test_foreign_address():
    p = parse_address("365 Sinseon-ro, Nam-gu, Busan,  48548, Korea, South (KOR)")
    assert p.country == "KOR"
    assert p.is_foreign is True
    assert p.state == ""


def test_territory_address():
    p = parse_address("Pridco Indus Park, SR 183, Las Piedras, Puerto Rico (PR) 00771, United States (USA)")
    assert p.country == "USA"
    assert p.state == "PR"
