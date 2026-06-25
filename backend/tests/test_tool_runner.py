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
