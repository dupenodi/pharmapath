"""Parse DECRS free-text addresses into structured (city, state, country) parts.

DECRS addresses follow a consistent tail format:
  domestic: "..., <City>, <State Name> (XX) <ZIP>, United States (USA)"
  foreign:  "..., <City>,  <ZIP>, <Country> (XXX)"
We only need the country (to flag foreign firms) and, for US firms, the
2-letter state code so the facility can be linked to a Geography node.
"""

import re
from dataclasses import dataclass

# Last 3-letter code in parentheses is the country (USA, IND, KOR, ...).
_COUNTRY = re.compile(r"\(([A-Z]{3})\)\s*$")
# A 2-letter code in parentheses is the US state/territory (IL, CA, PR, ...).
_STATE = re.compile(r"\(([A-Z]{2})\)")


@dataclass
class ParsedAddress:
    city: str
    state: str  # US 2-letter code, or "" for foreign/unknown
    country: str  # ISO-ish 3-letter (USA, IND, ...), or ""
    is_foreign: bool


def parse_address(address: str) -> ParsedAddress:
    addr = (address or "").strip()
    country_m = _COUNTRY.search(addr)
    country = country_m.group(1) if country_m else ""
    is_foreign = bool(country) and country != "USA"

    state = ""
    city = ""
    if not is_foreign:
        state_m = _STATE.search(addr)
        if state_m:
            state = state_m.group(1)
            # Format before the code is "..., <City>, <State Name>"; the city is
            # the comma-segment before the spelled-out state name.
            before = addr[: state_m.start()].rstrip(" ,")
            parts = [p.strip() for p in before.split(",") if p.strip()]
            if len(parts) >= 2:
                city = parts[-2]
    return ParsedAddress(city=city, state=state, country=country, is_foreign=is_foreign)
