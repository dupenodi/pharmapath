"""Classify an NDC labeler as a real manufacturer vs a repackager/relabeler.

The openFDA NDC directory's `labeler_name` is whoever holds the NDC labeler
code, which is frequently a repackaging pharmacy, not the drug's maker (see
PLAN.md assumption 10). Repackagers account for ~24% of prescription rows and
dominate the manufacturer graph by volume, so we annotate them rather than
treat them as manufacturers. This is a heuristic; once DECRS is ingested its
`facility_type` ("repack"/"relabel") becomes the authoritative signal and this
module becomes a fallback for labelers DECRS doesn't cover.
"""

import re

# Labelers we know are repackagers/relabelers (the high-volume ones the
# heuristic might otherwise miss or that we want to be explicit about).
KNOWN_REPACKAGERS = frozenset(
    {
        "bryant ranch prepack",
        "a-s medication solutions",
        "proficient rx lp",
        "remedyrepack inc.",
        "nucare pharmaceuticals,inc.",
        "nucare pharmaceuticals, inc.",
        "pd-rx pharmaceuticals, inc.",
        "aphena pharma solutions - tennessee, llc",
        "preferred pharmaceuticals inc.",
        "preferred pharmaceuticals, inc.",
        "golden state medical supply, inc.",
        "american health packaging",
        "advanced rx pharmacy of tennessee, llc",
        "st. mary's medical park pharmacy",
        "redpharm drug",
        "redpharm drug, inc.",
        "clinical solutions wholesale, llc",
        "direct rx",
        "denton pharma, inc. dba northwind pharmaceuticals",
        "northwind pharmaceuticals",
        "quality care products, llc",
        "rebel distributors corp.",
        "physicians total care, inc.",
        "lake erie medical dba quality care products llc",
        "unit dose services",
        "major pharmaceuticals",
    }
)

# Token patterns that strongly indicate repackaging/relabeling/dispensing rather
# than manufacturing. Word-boundaried to avoid matching real maker names.
# Leading \b only -- a trailing boundary would miss stems like "Repackaging".
_REPACKAGER_PATTERN = re.compile(
    r"\b(re-?pack|pre-?pack|unit dose|medication solutions|"
    r"medical park pharmacy|dispensing|relabel)",
    re.IGNORECASE,
)


def is_repackager(labeler_name: str, canonical_name: str | None = None) -> bool:
    """True if this labeler looks like a repackager/relabeler, not a manufacturer."""
    raw = (labeler_name or "").strip().lower()
    if raw in KNOWN_REPACKAGERS:
        return True
    if canonical_name and canonical_name.strip().lower() in KNOWN_REPACKAGERS:
        return True
    return bool(_REPACKAGER_PATTERN.search(labeler_name or ""))


def classify_entity(labeler_name: str, canonical_name: str | None = None) -> str:
    """Return 'repackager' or 'manufacturer' for an NDC labeler."""
    return "repackager" if is_repackager(labeler_name, canonical_name) else "manufacturer"
