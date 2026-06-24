import re

from rapidfuzz import fuzz

_LEGAL_SUFFIXES = re.compile(
    r"\b(llc|l\.l\.c|inc|incorporated|corp|corporation|ltd|limited|co|company|"
    r"pharmaceuticals?|pharma|laboratories|labs?|holdings?|group|usa|us)\b\.?",
    re.IGNORECASE,
)
_PUNCTUATION = re.compile(r"[.,'\"()&/-]")
_WHITESPACE = re.compile(r"\s+")

NAME_MATCH_THRESHOLD = 90.0


def normalize_name(raw_name: str) -> str:
    """Lowercase, strip legal suffixes/punctuation, collapse whitespace.

    Used to build a canonical key for manufacturer/distributor names that
    are spelled inconsistently across NDC, DECRS, and DSCSA (e.g. "Amneal
    Pharmaceuticals LLC" vs "AMNEAL PHARMS").
    """
    name = raw_name.lower().strip()
    name = _PUNCTUATION.sub(" ", name)
    name = _LEGAL_SUFFIXES.sub(" ", name)
    name = _WHITESPACE.sub(" ", name).strip()
    return name


def names_match(name_a: str, name_b: str, threshold: float = NAME_MATCH_THRESHOLD) -> bool:
    """True if two raw names are the same entity at the project's 90% threshold."""
    score = fuzz.token_sort_ratio(normalize_name(name_a), normalize_name(name_b))
    return score >= threshold


def best_match(raw_name: str, candidates: list[str], threshold: float = NAME_MATCH_THRESHOLD) -> str | None:
    """Returns the candidate (from `candidates`) that best matches `raw_name`, or None."""
    target = normalize_name(raw_name)
    best_candidate: str | None = None
    best_score = 0.0
    for candidate in candidates:
        score = fuzz.token_sort_ratio(target, normalize_name(candidate))
        if score > best_score:
            best_score = score
            best_candidate = candidate
    return best_candidate if best_score >= threshold else None
