from app.agent.tool_runner import fallback_render_component


def test_fallback_synthesizes_disambiguation_prompt_when_ambiguous():
    tool_calls_log = [
        {
            "name": "resolve_drug",
            "input": {"drug_name": "Acetaminophen"},
            "result": {
                "ambiguous": True,
                "disambiguation_options": [
                    {"drug_id": "drug:1", "label": "Acetaminophen 10 mg/mL INJECTION"},
                    {"drug_id": "drug:2", "label": "Acetaminophen 1000 mg/100mL INJECTION"},
                ],
            },
        }
    ]

    fallback = fallback_render_component(tool_calls_log, "find me acetaminophen")

    assert fallback is not None
    component, data = fallback
    assert component == "disambiguation_prompt"
    assert data == {
        "query": "find me acetaminophen",
        "options": [
            {"drug_id": "drug:1", "label": "Acetaminophen 10 mg/mL INJECTION"},
            {"drug_id": "drug:2", "label": "Acetaminophen 1000 mg/100mL INJECTION"},
        ],
    }


def test_fallback_returns_none_when_not_ambiguous():
    tool_calls_log = [
        {
            "name": "resolve_drug",
            "input": {"drug_name": "Acetaminophen 500mg tablet"},
            "result": {"ambiguous": False, "drug_ids": ["drug:1"]},
        }
    ]

    assert fallback_render_component(tool_calls_log, "find acetaminophen 500mg tablet") is None


def test_fallback_returns_none_when_no_resolve_drug_call():
    assert fallback_render_component([], "hello") is None


def test_fallback_synthesizes_supplier_table_from_match_suppliers():
    tool_calls_log = [
        {"name": "resolve_drug", "input": {}, "result": {"ambiguous": False, "drug_ids": ["drug:1"]}},
        {"name": "check_shortage", "input": {}, "result": {"drug_id": "drug:1", "shortages": []}},
        {
            "name": "match_suppliers",
            "input": {},
            "result": {
                "matches": [{"supplier_id": "dist:mckesson", "supplier_name": "McKesson", "score": 0.9}],
                "explanation": "Best match by compliance and coverage.",
            },
        },
    ]

    fallback = fallback_render_component(tool_calls_log, "find me a supplier")

    assert fallback == (
        "supplier_table",
        {
            "matches": [{"supplier_id": "dist:mckesson", "supplier_name": "McKesson", "score": 0.9}],
            "explanation": "Best match by compliance and coverage.",
        },
    )


def test_fallback_synthesizes_risk_card_from_check_shortage_when_no_match_suppliers():
    tool_calls_log = [
        {
            "name": "resolve_drug",
            "input": {},
            "result": {"ambiguous": False, "drug_ids": ["drug:1"], "drugs": [{"generic_name": "Acetaminophen"}]},
        },
        {
            "name": "check_shortage",
            "input": {},
            "result": {"drug_id": "drug:1", "shortages": [{"status": "active", "reason": "Manufacturing delay"}]},
        },
    ]

    fallback = fallback_render_component(tool_calls_log, "is this drug at risk?")

    assert fallback == (
        "risk_card",
        {
            "drug_name": "Acetaminophen",
            "risk_summary": {
                "overall_risk": "high",
                "shortage_active": True,
                "manufacturers_flagged": 0,
                "manufacturers_total": 0,
                "risk_flags": ["Manufacturing delay"],
            },
            "shortages": [{"status": "active", "reason": "Manufacturing delay"}],
        },
    )


def test_fallback_synthesizes_supply_chain_graph():
    tool_calls_log = [
        {
            "name": "get_supply_chain",
            "input": {},
            "result": {"nodes": [{"id": "drug:1", "type": "Drug"}], "edges": []},
        }
    ]

    assert fallback_render_component(tool_calls_log, "show me the supply chain") == (
        "supply_chain_graph",
        {"nodes": [{"id": "drug:1", "type": "Drug"}], "edges": []},
    )


def test_fallback_synthesizes_map_view():
    tool_calls_log = [
        {
            "name": "get_distributor_coverage",
            "input": {"state": "TX"},
            "result": {"state": "TX", "distributors": [{"id": "dist:mckesson"}]},
        }
    ]

    assert fallback_render_component(tool_calls_log, "who covers Texas?") == (
        "map_view",
        {"state": "TX", "distributors": [{"id": "dist:mckesson"}]},
    )
