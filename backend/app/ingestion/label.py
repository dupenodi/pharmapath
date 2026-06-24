import re

_LEADING_LABEL_RE = re.compile(r"^.*?inactive ingredients?[:\s]*", re.IGNORECASE)


def parse_inactive_ingredients(label: dict) -> list[str]:
    """Splits a label's free-text inactive_ingredient section into excipient names.

    Active ingredients come from the NDC directory's structured
    active_ingredients array (already used for Drug.substance_name) -- this
    only covers excipients, which NDC doesn't list, for CONTAINS{is_active:false}.
    """
    blocks = label.get("inactive_ingredient", [])
    names: list[str] = []
    for block in blocks:
        text = _LEADING_LABEL_RE.sub("", block).strip()
        for chunk in re.split(r"[;,]", text):
            name = chunk.strip().rstrip(".")
            if name and len(name) < 60:
                names.append(name)
    return names
