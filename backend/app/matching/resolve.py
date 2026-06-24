from dataclasses import dataclass

import networkx as nx
from rapidfuzz import fuzz

FUZZY_MATCH_THRESHOLD = 65.0


@dataclass
class DrugResolution:
    drug_ids: list[str]
    ambiguous: bool
    disambiguation_options: list[dict]  # [{"drug_id", "label"}] when ambiguous


def _drug_label(node: dict) -> str:
    parts = [node.get("brand_name") or node.get("generic_name", ""), node.get("strength", ""), node.get("dosage_form", "")]
    return " ".join(p for p in parts if p)


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
                fuzz.partial_ratio(query, d.get("generic_name", "").lower()),
                fuzz.partial_ratio(query, (d.get("brand_name") or "").lower()),
            )
            if name_score >= FUZZY_MATCH_THRESHOLD:
                fuzzy_scores.append((n, name_score))
        if fuzzy_scores:
            candidates = [n for n, _ in fuzzy_scores]
        else:
            # Step 3: fall back to active ingredient (substance) match
            candidates = [
                n
                for n, d in drug_nodes
                if any(query in s.lower() or fuzz.partial_ratio(query, s.lower()) >= FUZZY_MATCH_THRESHOLD for s in d.get("substance_name", []))
            ]

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
        seen: set[tuple[str | None, str | None]] = set()
        options = []
        for n in candidates:
            combo = (graph.nodes[n].get("strength"), graph.nodes[n].get("dosage_form"))
            if combo in seen:
                continue
            seen.add(combo)
            options.append({"drug_id": n, "label": _drug_label(graph.nodes[n])})
        return DrugResolution(drug_ids=[n for n in candidates], ambiguous=True, disambiguation_options=options)

    return DrugResolution(drug_ids=candidates, ambiguous=False, disambiguation_options=[])
