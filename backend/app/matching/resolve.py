import re
from dataclasses import dataclass

import networkx as nx
from rapidfuzz import fuzz

FUZZY_MATCH_THRESHOLD = 80.0
MAX_FUZZY_CANDIDATES = 50
MAX_DISAMBIGUATION_OPTIONS = 12

_WORD_SPLIT = re.compile(r"[\s,\-/;:]+")

# resolve_drug expects a drug name, not a sentence, but a model can still
# pass one (e.g. "let's go with the 80mg tablet, drug id drug:123" was seen
# live). Filtering common English/instruction words before word-matching
# stops them from coincidentally exact-matching the same word inside an
# unrelated product name (e.g. "drug" inside "Discount Drug Mart").
_STOPWORDS = {
    "a", "an", "the", "is", "are", "for", "with", "go", "lets", "let's", "to",
    "drug", "id", "this", "that", "of", "and", "or", "please", "use", "it",
}


@dataclass
class DrugResolution:
    drug_ids: list[str]
    ambiguous: bool
    disambiguation_options: list[dict]  # [{"drug_id", "label"}] when ambiguous
    disambiguation_total: int = 0  # true count of distinct combos, before any cap


def _drug_label(node: dict) -> str:
    parts = [node.get("brand_name") or node.get("generic_name", ""), node.get("strength", ""), node.get("dosage_form", "")]
    return " ".join(p for p in parts if p)


def _word_match(query: str, candidate: str) -> float:
    """Best similarity between any word of the query and any word of the
    candidate name. Word-level, not whole-string, in either direction --
    comparing full strings (even with RapidFuzz's blended WRatio) let a
    handful of shared characters between long/messy text and a short name
    score deceptively high (a query containing a stray drug ID and dosage
    once matched ~1,880 unrelated drugs at the whole-string level, ranking
    nonsense like "Stannum metallicum" above the real answer). Comparing
    word-to-word means an unrelated filler word can only ever match another
    short, unrelated word -- it can't borrow length/score from the rest of
    the string."""
    qwords = [w for w in _WORD_SPLIT.split(query) if len(w) > 2 and w not in _STOPWORDS and not w.isdigit()]
    cwords = [w for w in _WORD_SPLIT.split(candidate) if len(w) > 2 and not w.isdigit()]
    if not qwords or not cwords:
        return 0.0
    return max(fuzz.ratio(qw, cw) for qw in qwords for cw in cwords)


def resolve_drug(
    graph: nx.MultiDiGraph,
    drug_name: str,
    dosage_form: str | None = None,
    strength: str | None = None,
    prefer_generic: bool = False,
) -> DrugResolution:
    """Resolves free-text drug input to Drug node(s), per PLAN.md's 5-step algorithm.

    Step 1: exact match on generic_name.
    Step 2: fuzzy match on brand_name/generic_name.
    Step 3: fall back to matching by active ingredient (substance_name).
    Step 4: if multiple distinct strength/form combos remain, disambiguate.
    Step 5: if prefer_generic, filter to is_generic.
    """
    query = drug_name.strip().lower()
    drug_nodes = [(n, d) for n, d in graph.nodes(data=True) if d.get("type") == "Drug" and d.get("status") == "active"]

    exact = [n for n, d in drug_nodes if d.get("generic_name", "").lower() == query or (d.get("brand_name") or "").lower() == query]

    if exact:
        candidates = exact
    else:
        fuzzy_scores = []
        for n, d in drug_nodes:
            name_score = max(
                _word_match(query, d.get("generic_name", "").lower()),
                _word_match(query, (d.get("brand_name") or "").lower()),
            )
            if name_score >= FUZZY_MATCH_THRESHOLD:
                fuzzy_scores.append((n, name_score))
        if fuzzy_scores:
            # Best matches first, and capped -- without this, a sufficiently
            # messy query can still produce dozens of weak word-level
            # coincidences; ranking by score and capping means the real
            # answer (if any) survives even when noise also clears the bar.
            fuzzy_scores.sort(key=lambda ns: ns[1], reverse=True)
            candidates = [n for n, _ in fuzzy_scores[:MAX_FUZZY_CANDIDATES]]
        else:
            # Step 3: fall back to active ingredient (substance) match
            candidates = [
                n
                for n, d in drug_nodes
                if any(query in s.lower() or _word_match(query, s.lower()) >= FUZZY_MATCH_THRESHOLD for s in d.get("substance_name", []))
            ][:MAX_FUZZY_CANDIDATES]

    if not candidates:
        return DrugResolution(drug_ids=[], ambiguous=False, disambiguation_options=[])

    if dosage_form:
        # Hard filter: never silently widen back out if this eliminates everything --
        # that would mean guessing a formulation the user didn't ask for.
        candidates = [n for n in candidates if (graph.nodes[n].get("dosage_form") or "").lower() == dosage_form.lower()]
    if strength:
        candidates = [
            n
            for n in candidates
            if strength.lower().replace(" ", "") in (graph.nodes[n].get("strength") or "").lower().replace(" ", "")
        ]
    if not candidates:
        return DrugResolution(drug_ids=[], ambiguous=False, disambiguation_options=[])
    if prefer_generic:
        filtered = [n for n in candidates if graph.nodes[n].get("is_generic")]
        if filtered:
            candidates = filtered

    distinct_combos = {(graph.nodes[n].get("strength"), graph.nodes[n].get("dosage_form")) for n in candidates}
    if len(distinct_combos) > 1 and not (dosage_form and strength):
        # Don't guess the formulation -- surface disambiguation options.
        # candidates is already best-match-first from the fuzzy ranking above
        # (or all-equal exact matches), so capping here keeps the strongest
        # options when there happen to be many distinct combos.
        seen: set[tuple[str | None, str | None]] = set()
        options = []
        for n in candidates:
            combo = (graph.nodes[n].get("strength"), graph.nodes[n].get("dosage_form"))
            if combo in seen:
                continue
            seen.add(combo)
            options.append({"drug_id": n, "label": _drug_label(graph.nodes[n])})
        return DrugResolution(
            drug_ids=[n for n in candidates],
            ambiguous=True,
            disambiguation_options=options[:MAX_DISAMBIGUATION_OPTIONS],
            disambiguation_total=len(options),
        )

    return DrugResolution(drug_ids=candidates, ambiguous=False, disambiguation_options=[])
