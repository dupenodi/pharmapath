TOOLS = [
    {
        "name": "resolve_drug",
        "description": "Resolves a free-text drug name to one or more Drug nodes in the graph. Always call this first when the user mentions a drug.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name": {"type": "string"},
                "dosage_form": {"type": "string"},
                "strength": {"type": "string"},
                "prefer_generic": {"type": "boolean"},
            },
            "required": ["drug_name"],
        },
    },
    {
        "name": "get_supply_chain",
        "description": "Returns the full supply chain subgraph for a drug: active ingredient to manufacturer to facility to geography. Use when the user wants to understand or visualize the chain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_id": {"type": "string"},
                "include_compliance": {"type": "boolean"},
            },
            "required": ["drug_id"],
        },
    },
    {
        "name": "get_compliance_status",
        "description": "Fetches live compliance status for a manufacturer from openFDA. Always call before surfacing any supplier as a match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["manufacturer", "facility"]},
            },
            "required": ["entity_id", "entity_type"],
        },
    },
    {
        "name": "check_shortage",
        "description": "Checks openFDA for active drug shortages. Call for any procurement request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name": {"type": "string"},
                "drug_id": {"type": "string"},
            },
            "required": ["drug_id"],
        },
    },
    {
        "name": "find_alternatives",
        "description": "Returns drugs that share an active ingredient with the given drug (therapeutic/generic equivalence data from the Orange Book is not yet ingested -- see caveats in the response). Use when shortage is active or the user asks for alternatives.",
        "input_schema": {
            "type": "object",
            "properties": {"drug_id": {"type": "string"}},
            "required": ["drug_id"],
        },
    },
    {
        "name": "match_suppliers",
        "description": "Runs the matching engine. Returns a ranked supplier list with compliance and risk. Use when the user has a procurement need.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_id": {"type": "string"},
                "delivery_state": {"type": "string"},
                "quantity": {"type": "integer"},
                "deadline_days": {"type": "integer"},
                "prefer_generic": {"type": "boolean"},
            },
            "required": ["drug_id", "delivery_state"],
        },
    },
    {
        "name": "get_distributor_coverage",
        "description": "Returns all licensed wholesale distributors for a given US state.",
        "input_schema": {
            "type": "object",
            "properties": {"state": {"type": "string"}},
            "required": ["state"],
        },
    },
    {
        "name": "render_component",
        "description": "Tells the frontend which UI component to render. Always call this as the final step.",
        "input_schema": {
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "enum": [
                        "supply_chain_graph",
                        "supplier_table",
                        "risk_card",
                        "map_view",
                        "comparison_card",
                        "disambiguation_prompt",
                    ],
                },
                "data": {"type": "object"},
            },
            "required": ["component", "data"],
        },
    },
]
