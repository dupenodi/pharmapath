_DRUG_ID_DESC = "Drug node ID including its 'drug:' prefix (e.g. 'drug:0480-3588'), exactly as returned in resolve_drug's drug_ids/drugs or a disambiguation_options entry -- never just the bare NDC number."

TOOLS = [
    {
        "name": "resolve_drug",
        "description": "Resolves a free-text drug name to one or more Drug nodes in the graph. Always call this first when the user mentions a drug.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name": {
                    "type": "string",
                    "description": "The drug name only (e.g. 'atorvastatin' or 'atorvastatin 80mg') -- not a full sentence and not a drug_id you already have.",
                },
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
                "drug_id": {"type": "string", "description": _DRUG_ID_DESC},
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
                "entity_id": {
                    "type": "string",
                    "description": "Node ID including its type prefix (e.g. 'mfr:pfizer' or 'facility:1234567'), exactly as it appears in another tool's result.",
                },
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
            "properties": {"drug_id": {"type": "string", "description": _DRUG_ID_DESC}},
            "required": ["drug_id"],
        },
    },
    {
        "name": "find_alternatives",
        "description": "Returns Orange Book-confirmed therapeutic equivalents (same TE code group) for a drug -- genuine substitutes, not just same-ingredient matches. Use when a shortage is active or the user asks for alternatives.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_id": {"type": "string", "description": _DRUG_ID_DESC},
                "cap": {
                    "type": "integer",
                    "description": "Max alternatives to return (default 24). The response also reports the true total, which is often larger.",
                },
            },
            "required": ["drug_id"],
        },
    },
    {
        "name": "match_suppliers",
        "description": "Runs the matching engine. Returns a ranked supplier list with compliance and risk. Use when the user has a procurement need.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_id": {"type": "string", "description": _DRUG_ID_DESC},
                "delivery_state": {"type": "string", "description": "Two-letter US state code (e.g. 'IL')."},
                "quantity": {"type": "integer"},
                "deadline_days": {"type": "integer"},
                "prefer_generic": {"type": "boolean"},
            },
            "required": ["drug_id", "delivery_state"],
        },
    },
    {
        "name": "get_distributor_coverage",
        "description": "Returns licensed wholesale distributors for a given US state, national-coverage carriers first. Populous states can have hundreds of licensees -- the response is capped (default 20) and reports the true total, so don't assume the list is exhaustive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Two-letter US state code (e.g. 'IL')."},
                "limit": {"type": "integer", "description": "Max distributors to return (default 20)."},
            },
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
