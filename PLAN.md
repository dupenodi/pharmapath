# EaseMed POC — Pharma Supply Chain Intelligence Platform
**Author:** Sarath Donepudi  
**Status:** Draft  
**Created:** 2026-06-24  
**Version:** 2.0

---

## Summary

A proof-of-concept for EaseMed's core intelligence layer — a pharma supply chain knowledge graph covering the US market, a matching engine that scores and ranks verified suppliers against hospital procurement requests, and an agent + generative UI layer for natural language interaction. All three layers are demonstrated end to end using public FDA datasets with Acetaminophen as the primary demo drug.

---

## Problem

Hospital procurement teams operate blind:

- No structured map of who manufactures a given drug, where, under what compliance status
- No way to go from "I need X" to "here are verified, ranked suppliers" without making phone calls
- Shortage awareness is reactive — hospitals find out a drug is unavailable after stock runs out, not before
- The distributor layer is relationship-based and opaque — no public structured data on who distributes what to where
- When one manufacturer has a compliance issue, procurement teams don't know which drugs are affected or what alternatives exist

EaseMed's value proposition is proactive supply chain intelligence. The POC needs to prove that a system can ingest public data, build a meaningful graph, run intelligent matching, and surface the right answer in the right visual format — all from a natural language prompt.

---

## Scope

**In scope:**
- US pharmaceutical supply chain only
- Prescription drugs (FDA-regulated, NDC-listed)
- Knowledge graph: active ingredient to drug/brand to manufacturer to facility to distributor to geography
- Matching engine: structured procurement request to scored, ranked supplier list with risk signals
- Agent: natural language to tool calls to graph traversal to structured answer
- GenUI: agent-selected visual components rendered in the frontend

**Out of scope for POC:**
- India or other country supply chains
- Real-time inventory levels or live pricing
- Hospital EHR/EMR integration
- User auth, multi-tenancy, billing
- Over-the-counter drugs (OTCs are in the NDC but de-prioritised)
- Biological products, blood products, devices
- Production-grade data pipelines or scheduled refresh

---

## Assumptions

These are reasonable assumptions made to move forward. Each should be validated with Nikita before productionising.

1. **Distributors don't carry all drugs.** We assume the big 3 wholesale distributors (McKesson, Cardinal Health, AmerisourceBergen) have broad coverage across most FDA-approved drugs. For the POC, if a drug has a licensed distributor that covers the delivery state, we treat them as a candidate match. We are not modelling which specific SKUs each distributor carries — that data is not public.

2. **Manufacturer = potential direct supplier.** In reality, manufacturers rarely sell direct to hospitals. For the POC, we include manufacturers as potential suppliers with a lower base score than distributors, to reflect this.

3. **Compliance = binary for scoring.** We score compliance as clean (no active flags) or flagged (at least one active recall, import alert, or GMP violation in the last 24 months). In production, severity, scope, and recency would be weighted continuously.

4. **Location score = distance proxy.** We use straight-line distance between distributor/facility state centroid and delivery location. In production this would use actual logistics routing and transit times.

5. **Shortage = drug-level, not SKU-level.** The openFDA shortage endpoint reports shortages at the drug name level, not by NDC. We assume a shortage on "Acetaminophen 500mg tablet" affects all brands of that formulation.

6. **DSCSA database = authoritative distributor list.** We treat FDA's DSCSA annual reporting database as the ground truth for licensed wholesale distributors. A distributor not in this list is not surfaced as a match.

7. **Orange Book equivalence = safe alternative.** If the requested drug has an Orange Book therapeutic equivalent, we surface it as an alternative. We assume the procurement team's clinical staff validates actual substitutability.

8. **Entity name matching is fuzzy.** Manufacturer names across NDC, DECRS, and DSCSA datasets are not consistently formatted. We normalise using fuzzy string matching (RapidFuzz) and treat matches above 90% similarity as the same entity.

9. **Graph is static within a session.** The graph is seeded from FDA bulk downloads at startup. Compliance and shortage signals are fetched live from openFDA per query. The graph itself is not refreshed mid-session in the POC.

10. **NDC labeler = manufacturer.** The NDC labeler code identifies who packaged and labelled the drug, which is often the same as the manufacturer but not always (repackagers exist). For the POC we treat the labeler as the responsible manufacturer, with a repackager annotation where detectable.

---

## Data Sources

All public, free, no scraping required.

| Dataset | Source | Format | What it provides | Refresh cadence |
|---|---|---|---|---|
| NDC Directory | openFDA bulk download | JSON/CSV | Every listed drug: NDC code, brand name, generic name, dosage form, strength, labeler | Monthly |
| Drug label data | openFDA /drug/label API | JSON | Active ingredients, inactive ingredients, indications, warnings | Live API |
| Orange Book | FDA download | Text delimited | Approved drugs, therapeutic equivalents, generics, patent expiry | Monthly |
| DECRS | data.gov dataset | CSV | Every registered drug manufacturing facility: name, address, city, state, zip, registration status | Periodic |
| DSCSA wholesale distributor DB | FDA annual reporting | CSV | Every licensed wholesale drug distributor and 3PL: name, facility address, states licensed, license type | Daily |
| Drug shortages | openFDA /drug/drugshortages API | JSON | Active and resolved shortages: drug name, reason, status, affected firms | Live API |
| Enforcement/recalls | openFDA /drug/enforcement API | JSON | Recall events: product, firm, reason, Class I/II/III, date | Live API |
| FDA import alerts | FDA website | HTML parsed | Manufacturers banned from US import: firm name, country, reason | Periodic |
| Drugs@FDA | FDA bulk download | ZIP/text | Application numbers, approval dates, applicant names | Monthly |

### Data quality issues and mitigations

**NDC labeler is not always the manufacturer**
Some entries are repackagers. Cross-reference NDC labeler against DECRS. If the labeler's registered facility type includes "repackager", downgrade in scoring and annotate the node.

**Manufacturer name inconsistency across datasets**
"Amneal Pharmaceuticals LLC" vs "Amneal Pharmaceuticals" vs "AMNEAL PHARMS". Normalise to lowercase, strip legal suffixes (LLC, Inc, Ltd, Corp), apply RapidFuzz token sort ratio. Threshold: 90% = same entity. Build a canonical name index at ingestion time.

**DECRS has facilities without clear drug associations**
DECRS lists every registered facility but doesn't say which drugs they make. Join DECRS facilities to NDC labelers via fuzzy name match. Where no match found, facility is ingested but flagged as unlinked.

**openFDA shortage endpoint uses drug names inconsistently**
"Acetaminophen" may miss entries filed as "Acetaminophen and Codeine" or "APAP". Search by generic name and all known synonyms. Maintain a synonym map for common drugs.

**FDA import alerts are not structured data**
HTML pages, not an API. Pre-scrape and cache import alert data for the top 500 manufacturers at ingestion time. Flag as "import alert data unavailable" for manufacturers not in cache.

---

## Knowledge Graph — Detailed Design

### Node schemas

**ActiveIngredient**
```
id:          string (CAS number or openFDA substance ID)
name:        string (canonical, e.g. "Acetaminophen")
synonyms:    string[] (["APAP", "Paracetamol", "N-acetyl-p-aminophenol"])
drug_class:  string
```

**Drug**
```
id:             string (NDC product code, first 9 digits)
ndc_full:       string (full 10-digit NDC)
brand_name:     string
generic_name:   string
dosage_form:    string (tablet, capsule, injectable, etc.)
strength:       string ("500mg", "10mg/5ml")
route:          string (oral, intravenous, topical)
labeler_name:   string
application_no: string (NDA/ANDA number)
is_generic:     boolean
otc:            boolean
status:         enum [active, discontinued, withdrawn]
```

**Manufacturer**
```
id:             string (generated canonical ID)
canonical_name: string
raw_names:      string[] (all name variants seen across datasets)
duns_number:    string (if available)
country:        string
is_foreign:     boolean
type:           enum [manufacturer, repackager, relabeler]
```

**Facility**
```
id:                  string (DECRS FEI number)
name:                string
address:             string
city:                string
state:               string
zip:                 string
lat:                 float
lng:                 float
country:             string
registration_status: enum [active, inactive, pending]
facility_type:       string[] (manufacture, repack, relabel, etc.)
```

**Distributor**
```
id:               string (DSCSA license number)
name:             string
canonical_name:   string
type:             enum [wholesale_distributor, third_party_logistics]
facility_address: string
city:             string
state:            string (home state)
states_licensed:  string[]
national_coverage: boolean (licensed in 40+ states)
```

**Geography**
```
id:           string (state code, e.g. "IL")
name:         string
centroid_lat: float
centroid_lng: float
region:       string (midwest, northeast, etc.)
```

**Shortage**
```
id:             string
drug_name:      string
generic_name:   string
status:         enum [active, resolved]
reason:         string
start_date:     date
resolved_date:  date | null
affected_firms: string[]
source:         "openFDA"
last_checked:   timestamp
```

**ComplianceFlag**
```
id:                string
type:              enum [recall, import_alert, gmp_violation, warning_letter]
severity:          enum [critical, high, medium, low]
  // recall Class I = critical | Class II = high | Class III = medium
  // import_alert = high | warning_letter = medium
status:            enum [active, closed]
issued_date:       date
closed_date:       date | null
description:       string
source_url:        string
affected_products: string[]
```

### Edge schema

```
(Drug)-[:CONTAINS {is_active: true}]->(ActiveIngredient)
(Drug)-[:CONTAINS {is_active: false}]->(ActiveIngredient)   // excipients
(Drug)-[:LABELLED_BY]->(Manufacturer)
(Manufacturer)-[:OPERATES]->(Facility)
(Facility)-[:LOCATED_IN]->(Geography)
(Distributor)-[:LICENSED_IN]->(Geography)
(Manufacturer)-[:HAS_FLAG {active: bool}]->(ComplianceFlag)
(Facility)-[:HAS_FLAG {active: bool}]->(ComplianceFlag)     // facility-level flags
(Drug)-[:HAS_SHORTAGE {active: bool}]->(Shortage)
(Drug)-[:EQUIVALENT_TO {type: "therapeutic"}]->(Drug)
(Drug)-[:EQUIVALENT_TO {type: "generic"}]->(Drug)
```

Note: DISTRIBUTES edge between Distributor and Drug is NOT modelled. No public data confirms which distributor carries which specific drug. Distributor candidates are resolved at query time by license coverage.

### Graph construction pipeline

```
Step 1: Ingest NDC bulk download
  For each NDC product:
    Upsert Drug node (deduplicate by 9-digit product code)
    Upsert Manufacturer node (canonical name resolution)
    Create LABELLED_BY edge

Step 2: Parse drug label API (batch for demo drugs only in POC)
  For each drug in demo set:
    Extract active_ingredients from label
    Upsert ActiveIngredient nodes
    Create CONTAINS edges (is_active=true for APIs, false for excipients)

Step 3: Ingest DECRS
  For each facility:
    Upsert Facility node (keyed on FEI number)
    Fuzzy match facility name to Manufacturer node
    If match >= 90%: create OPERATES edge
    If no match: ingest as unlinked Facility node, flagged
    Geocode address to lat/lng
    Create LOCATED_IN edge to Geography node

Step 4: Ingest Orange Book
  For each therapeutic equivalence entry:
    Resolve both drugs to existing Drug nodes
    Create EQUIVALENT_TO edges (bidirectional)

Step 5: Ingest DSCSA distributor database
  For each distributor entry:
    Upsert Distributor node
    Parse states_licensed field
    Create LICENSED_IN edges for each state

Step 6: Live compliance + shortage layer (per query, not seeded)
  On each agent query involving a drug or manufacturer:
    Hit openFDA /drug/enforcement for that manufacturer
    Hit openFDA /drug/drugshortages for that drug
    Upsert ComplianceFlag and Shortage nodes
    Attach edges to relevant Manufacturer/Drug nodes
    Cache result for 1 hour (TTL)
```

### Graph size estimate (POC)

| Node type | Estimated count |
|---|---|
| Drug (prescription only) | ~30,000 |
| ActiveIngredient | ~3,000 |
| Manufacturer | ~5,000 (after deduplication) |
| Facility | ~8,000 |
| Distributor | ~6,000 |
| Geography (states) | 51 |
| Shortage (active) | ~200-400 |
| ComplianceFlag | seeded lazily per query |

Total: ~50,000-70,000 nodes. networkx handles this comfortably in memory (~200-400MB RAM).

### Edge cases in graph construction

**Duplicate drugs under different NDCs:** Same drug may have 5 NDC codes for different package sizes. Deduplicate on 9-digit product code. Keep all NDC variants as ndc_full array on one Drug node.

**Discontinued drugs still in NDC directory:** Set status = discontinued. Do not surface in matching. Still include in graph for historical traversal.

**Manufacturer with multiple facilities:** All facilities linked via OPERATES edges. Compliance flags annotated at the Facility level, not just Manufacturer, because a flag on Facility A doesn't necessarily affect Facility B.

**Distributor licensed nationally but headquartered elsewhere:** Use states_licensed for coverage scoring. Use home state for physical location scoring.

**Drug has no Orange Book entry:** If no EQUIVALENT_TO edges exist, the alternatives fallback returns drugs sharing the same ActiveIngredient node, filtered by status = active.

**Import alert data missing for a manufacturer:** Surface as "compliance data unavailable" rather than "clean". Never assume clean.

---

## Matching Engine — Detailed Design

### When invoked

Called when the agent detects procurement intent: "I need X", "find me suppliers for Y", "who can deliver Z to Chicago". Not called for pure information queries like "show me the supply chain for X".

### Input schema

```python
@dataclass
class ProcurementRequest:
    drug_name: str                       # raw input, resolved to Drug node
    quantity: int | None                 # units requested (optional)
    dosage_form: str | None              # tablet, injectable, etc.
    strength: str | None                 # "500mg"
    delivery_state: str                  # required — 2-letter state code
    delivery_city: str | None            # optional — improves location scoring
    deadline_days: int | None            # optional — affects urgency modifier
    requirements: list[str]              # ["FDA_approved", "no_import_alert"]
    prefer_generic: bool = False
    resolved_drug_ids: list[str] = None  # set by agent after graph lookup
```

### Drug resolution (pre-matching step)

```
Input: "Acetaminophen 500mg tablet"

Step 1: Exact match on generic_name in graph
Step 2: If no exact match, fuzzy search on brand_name and generic_name (RapidFuzz)
Step 3: If still no match, search by ActiveIngredient name
Step 4: If multiple matches (different strengths/forms), return disambiguation prompt
Step 5: If prefer_generic=True, filter to is_generic=True nodes only
```

### Candidate supplier generation

```
For each resolved Drug node:

  Type A — Distributors:
    Get all Distributor nodes where delivery_state in states_licensed
    These are candidates. Cannot confirm they carry the specific drug.
    Annotate as "assumed available".

  Type B — Manufacturers (direct):
    Get Manufacturer nodes via LABELLED_BY edge from Drug
    Get their Facility nodes via OPERATES edge
    Check if any facility LOCATED_IN a state same as or adjacent to delivery_state
    Score lower than distributors by default.

  Type C — Alternatives:
    Get EQUIVALENT_TO edges from Drug node
    For each equivalent drug, run same candidate generation
    Tag as "alternative" in output
```

### Scoring function

```python
def score_candidate(candidate, request, graph) -> float | None:

    # 1. COMPLIANCE SCORE (weight: 0.40)
    flags = get_active_flags(candidate, graph)  # live openFDA call
    if any(f.severity == "critical" for f in flags):
        compliance_score = 0.0   # Class I recall
    elif any(f.severity == "high" for f in flags):
        compliance_score = 0.3   # Import alert
    elif any(f.severity == "medium" for f in flags):
        compliance_score = 0.7   # Warning letter
    else:
        compliance_score = 1.0   # Clean

    # 2. AVAILABILITY SCORE (weight: 0.25)
    shortage = check_shortage(request.resolved_drug_ids, graph)
    if shortage and candidate.name in shortage.affected_firms:
        availability_score = 0.0   # This supplier specifically named
    elif shortage:
        availability_score = 0.5   # Shortage exists but supplier not named
    else:
        availability_score = 1.0   # No active shortage

    # 3. LOCATION SCORE (weight: 0.25)
    distance_km = haversine(
        get_supplier_centroid(candidate),
        get_state_centroid(request.delivery_state)
    )
    if distance_km < 500:
        location_score = 1.0
    elif distance_km < 1500:
        location_score = 0.7
    elif distance_km < 3000:
        location_score = 0.4
    else:
        location_score = 0.2

    # 4. COVERAGE SCORE (weight: 0.10)
    if request.delivery_state in candidate.states_licensed:
        coverage_score = 1.0
    elif candidate.national_coverage:
        coverage_score = 0.8
    else:
        coverage_score = 0.0

    # HARD DISQUALIFIERS
    if coverage_score == 0.0:
        return None  # not licensed in delivery state
    if compliance_score == 0.0:
        return None  # Class I recall — excluded

    # BASE SCORE
    score = (
        compliance_score  * 0.40 +
        availability_score * 0.25 +
        location_score    * 0.25 +
        coverage_score    * 0.10
    )

    # URGENCY MODIFIER (deadline < 7 days: weight location more)
    if request.deadline_days and request.deadline_days < 7:
        score = (
            compliance_score  * 0.40 +
            availability_score * 0.20 +
            location_score    * 0.35 +
            coverage_score    * 0.05
        )

    return round(score, 3)
```

### Output schema

```python
@dataclass
class SupplierMatch:
    supplier_id: str
    supplier_name: str
    supplier_type: str            # "distributor" | "manufacturer_direct"
    score: float
    compliance_status: str        # "clean" | "flagged" | "unknown"
    active_flags: list[ComplianceFlag]
    licensed_in_state: bool
    states_licensed: list[str]
    shortage_risk: str            # "none" | "possible" | "confirmed"
    distance_km: float | None
    score_breakdown: dict         # {"compliance": 1.0, "availability": 0.5, ...}
    caveats: list[str]            # ["Stock availability not confirmed", ...]

@dataclass
class MatchResult:
    resolved_drug: Drug
    matches: list[SupplierMatch]  # sorted by score descending
    alternatives: list[AlternativeDrug]
    risk_summary: RiskSummary
    explanation: str

@dataclass
class RiskSummary:
    overall_risk: str             # "low" | "medium" | "high" | "critical"
    shortage_active: bool
    manufacturers_flagged: int
    manufacturers_total: int
    risk_flags: list[str]         # human-readable risk statements
```

### Edge cases in matching

**No candidates pass coverage filter:**
Return empty matches. Surface nearest licensed distributor even if wrong state with note: "No licensed distributors found in [state]. Nearest option: [distributor] licensed in [adjacent state]."

**All manufacturers have Class I recall:**
All candidates disqualified. Surface: "All known manufacturers of this drug have active Class I recalls. Showing alternatives." Run matching on EQUIVALENT_TO drugs.

**Drug is in shortage AND distributor availability is unknown:**
Score all distributors 0.5 on availability. Surface shortage prominently. Suggest alternatives first.

**Delivery state not specified:**
Do not guess. Return: "Please specify the delivery state to run supplier matching."

**Quantity > 50,000 units:**
No inventory data to validate. Add caveat: "For orders of this size, recommend contacting national distributors directly to confirm stock." Filter to national_coverage = true distributors only.

**Ambiguous drug input resolves to multiple nodes:**
e.g. "Acetaminophen" matches 500mg tablet AND 325mg tablet AND 650mg ER.
Return disambiguation before running matching. Do not guess the formulation.

**Compliance data is stale (pre-scraped > 7 days ago):**
Flag: "Compliance data may be outdated — last checked [date]. Verify with supplier before committing."

**Manufacturer is a repackager, not the original maker:**
Downgrade score by 0.1 and add caveat: "This supplier is a repackager, not the original manufacturer. Original manufacturer's compliance status may differ."

---

## Agent Layer — Detailed Design

### Tools

```python
tools = [

  {
    "name": "resolve_drug",
    "description": "Resolves a free-text drug name to one or more Drug nodes in the graph. Always call this first when the user mentions a drug.",
    "parameters": {
      "drug_name": "string",
      "prefer_generic": "boolean"
    }
  },

  {
    "name": "get_supply_chain",
    "description": "Returns the full supply chain subgraph for a drug: active ingredient to manufacturer to facility to geography. Use when user wants to understand or visualise the chain.",
    "parameters": {
      "drug_id": "string",
      "include_compliance": "boolean"
    }
  },

  {
    "name": "get_compliance_status",
    "description": "Fetches live compliance status for a manufacturer or facility from openFDA. Always call before surfacing any supplier as a match.",
    "parameters": {
      "entity_id": "string",
      "entity_type": "enum: manufacturer | facility"
    }
  },

  {
    "name": "check_shortage",
    "description": "Checks openFDA for active drug shortages. Call for any procurement request.",
    "parameters": {
      "drug_name": "string",
      "drug_id": "string"
    }
  },

  {
    "name": "find_alternatives",
    "description": "Returns therapeutic equivalents and generics using the Orange Book. Use when shortage is active or user asks for alternatives.",
    "parameters": {
      "drug_id": "string"
    }
  },

  {
    "name": "match_suppliers",
    "description": "Runs the matching engine. Returns ranked supplier list with compliance and risk. Use when user has a procurement need.",
    "parameters": {
      "drug_id": "string",
      "delivery_state": "string",
      "quantity": "integer",
      "deadline_days": "integer",
      "prefer_generic": "boolean"
    }
  },

  {
    "name": "get_distributor_coverage",
    "description": "Returns all licensed wholesale distributors for a given US state.",
    "parameters": {
      "state": "string"
    }
  },

  {
    "name": "render_component",
    "description": "Tells the frontend which UI component to render. Always call this as the final step.",
    "parameters": {
      "component": "enum: supply_chain_graph | supplier_table | risk_card | map_view | comparison_card | disambiguation_prompt",
      "data": "object"
    }
  }

]
```

### System prompt

```
You are EaseMed's pharmaceutical supply chain intelligence agent.
You help hospital procurement teams find verified suppliers,
understand supply chain risk, and make informed procurement decisions.

RULES:
1. Always call resolve_drug first when a user mentions a drug.
2. Always call get_compliance_status before surfacing any supplier.
3. Always call check_shortage for any procurement request.
4. Never present a supplier as clean if compliance data is unavailable. Say "unknown".
5. Never guess inventory availability. You don't have this data. Say so.
6. If all manufacturers have a Class I recall, surface alternatives immediately.
7. Always end by calling render_component with the most appropriate component.
8. Be direct about risk. Do not soften shortage or compliance warnings.
9. If the request is ambiguous (unclear drug, unclear location), ask before running matching.

COMPONENT SELECTION:
  User wants to understand a supply chain   -> supply_chain_graph
  User wants to find suppliers              -> supplier_table
  User asks about risk or shortage          -> risk_card
  User asks about geographic coverage       -> map_view
  User asks to compare two drugs/suppliers  -> comparison_card
  Drug name is ambiguous                    -> disambiguation_prompt
```

### Decision flow

```
User input
    |
    v
resolve_drug()
    |
    +-- Ambiguous? --> render disambiguation_prompt --> wait for user
    |
    v
Intent detection (LLM reasoning)
    |
    +-- "show chain / map / explain"
    |     get_supply_chain() + get_compliance_status() for each manufacturer
    |     render supply_chain_graph
    |
    +-- "find suppliers / I need / deliver"
    |     check_shortage()
    |     match_suppliers()
    |     if shortage: find_alternatives()
    |     render supplier_table (+ risk_card if high risk)
    |
    +-- "is X at risk / shortage"
    |     check_shortage() + get_compliance_status()
    |     render risk_card
    |
    +-- "who covers [state]"
    |     get_distributor_coverage()
    |     render map_view
    |
    +-- "compare X and Y"
          resolve_drug() x2 + get_supply_chain() x2
          render comparison_card
```

### Agent edge cases

**Drug not in graph:**
resolve_drug returns empty. Agent: "I couldn't find [drug name] in the FDA database. Could you check the spelling or provide the generic name?"

**Foreign drug not approved in the US:**
Agent: "This drug doesn't appear to be FDA-approved for the US market. I can search by active ingredient if you're looking for an equivalent."

**openFDA rate limited or down:**
Fall back to graph-cached compliance data if available. Flag: "Compliance data could not be verified in real time. Showing last known status from [date]."

**User provides brand name:**
resolve_drug handles this. Agent confirms: "Found [brand] — generic name is [X]. Showing results for all forms of [X]."

**Non-pharma question:**
"I'm specialised in pharmaceutical supply chain intelligence. I can help with drug supply chains, supplier matching, shortage risk, or compliance status."

---

## GenUI Layer — Detailed Design

### supply_chain_graph (Cytoscape.js)

```
Node colours:
  ActiveIngredient  purple
  Drug              blue
  Manufacturer      green (no flags) | red (active flag)
  Facility          teal (active) | grey (inactive)
  Distributor       orange
  Geography         light grey

Interactions:
  hover   tooltip with name, type, key properties
  click   side panel: full node details + compliance history
  right-click "Find suppliers using this manufacturer"

Edge labels:
  CONTAINS (active)    "active ingredient"
  CONTAINS (inactive)  "excipient"
  LABELLED_BY          "made by"
  OPERATES             "facility in [city, state]"
  LICENSED_IN          "licensed in [state]"

Red node click opens ComplianceFlag card:
  type, severity, description, issued date, source URL, affected products
```

### supplier_table

```
Columns: Rank | Supplier | Type | Score | Compliance | States | Shortage Risk | Caveats
Compliance badges: green=clean | yellow=medium flag | red=high/critical | grey=unknown
Sorted by score descending. User can re-sort by any column.
Row expand: shows score_breakdown and active_flags detail.
"Show alternatives" button appears if shortage_risk != "none".
```

### risk_card

```
Header: drug name + overall risk level (colour-coded banner)
Sections:
  Shortage Status    active/resolved/none + reason if active
  Manufacturer Risk  X of Y manufacturers have active flags
  Affected Suppliers list of flagged suppliers with flag type
  Alternatives       if shortage active, top 2 alternatives with risk levels
  Data freshness     "Compliance data last checked: [timestamp]"
```

### map_view (Mapbox GL JS)

```
Pins: one per distributor facility, colour-coded (green=clean, red=flagged, grey=unknown)
Delivery location: star pin at user's specified city/state
Pin click: distributor name, license number, states covered, compliance badge
Filters: by state | by type (wholesale vs 3PL) | by compliance status
```

### comparison_card

```
Side-by-side for two drugs or two suppliers:
For drugs: brand name, generic name, manufacturer, facility location,
           compliance status, shortage status, top distributor match
For suppliers: score, compliance, states covered, shortage risk, caveats
```

### disambiguation_prompt

```
"I found multiple matches for '[input]'. Which did you mean?"
[Button: Acetaminophen 325mg tablet]
[Button: Acetaminophen 500mg tablet]
[Button: Acetaminophen 650mg extended release tablet]
```

---

## API Design

```
POST /query
  Body:     { "message": string, "session_id": string }
  Response: {
    "agent_response": string,
    "component": string,
    "component_data": object,
    "tool_calls": ToolCall[],
    "warnings": string[]
  }

GET /graph/node/:id
  Response: full node object + all connected edges

GET /graph/supply-chain/:drug_id
  Response: subgraph of all nodes in the supply chain for this drug

GET /health
  Response: { "graph_loaded": bool, "node_count": int, "edge_count": int, "seeded_at": timestamp }
```

---

## Stack

| Layer | POC | Production path |
|---|---|---|
| Knowledge Graph | Python networkx in-memory | Neo4j or Amazon Neptune |
| Graph querying | networkx traversal | Cypher (Neo4j) |
| Matching Engine | Python dataclasses + scoring | Same, with DB-backed history |
| Name resolution | RapidFuzz fuzzy matching | Same + entity resolution model |
| Geocoding | geopy + Nominatim (free) | Google Maps Geocoding API |
| Distance calc | haversine library | Same |
| openFDA calls | httpx async client + 1hr TTL cache | Redis cache layer |
| Agent | Claude claude-sonnet-4-6, tool use | Same |
| Backend | FastAPI + Pydantic | Same |
| Frontend | Next.js 14, App Router | Same |
| Graph viz | Cytoscape.js | Same or D3-force |
| Map | Mapbox GL JS | Same |
| Deployment | Railway (backend), Vercel (frontend) | AWS/GCP |

---

## Trade-offs

| Decision | Gain | Give up |
|---|---|---|
| networkx in-memory | Zero infra, fast iteration | No persistence, ~400MB RAM, restarts lose graph |
| FDA public data only | Free, no auth, clean | No inventory data, US-only, no pricing |
| Lazy compliance fetching (per query) | Always fresh | ~300ms latency per openFDA call |
| Claude for agent | Best tool-use quality | API cost, slight latency |
| Distributor matching without SKU data | Shows full licensed landscape | Can't confirm actual stock |
| Fuzzy name matching at 90% threshold | Catches most name variants | Risk of false merges (e.g. "Teva" vs "Teva UK") |
| Static graph within session | Simple, predictable | Graph is stale until next startup |

---

## Open Questions

1. **Distributor scope:** All 6,000 DSCSA-licensed distributors, or just the big 3 nationals for the POC? Big 3 makes demo cleaner; all 6,000 is more realistic.
2. **Pricing:** Is price a factor in matching for the POC, or is compliance + availability + location enough?
3. **Resolved shortage risk:** Should a drug with a shortage resolved < 90 days ago still carry a risk flag? Recency matters for procurement trust.
4. **Quantity handling:** Since no inventory data exists, should large quantities (>50K units) trigger a "national distributor only" filter, or just a caveat?
5. **Supplier data writeback:** Should verified suppliers eventually be able to update their own nodes (inventory, pricing, capacity)? This is a major product architecture decision.

---

## Build Plan

**Day 1 — Data ingestion + graph**
- Download NDC bulk JSON, DECRS CSV, DSCSA CSV, Orange Book text files
- Write ingestion scripts with RapidFuzz name normalisation
- Seed networkx graph, validate node counts
- Write get_supply_chain() traversal function
- Expose GET /graph/supply-chain/:drug_id
- Validate: query Acetaminophen, confirm all manufacturers + facilities resolve

**Day 2 — Matching engine + agent**
- Implement scoring function with all 4 dimensions + urgency modifier
- Implement hard disqualifiers
- Implement all 8 agent tools
- Wire Claude (tool use) to all tools
- Implement live openFDA calls with 1hr TTL cache
- Expose POST /query
- Validate: "Find me suppliers for Acetaminophen 500mg in Illinois" returns ranked table

**Day 3 — Frontend + GenUI + demo polish**
- Next.js app with chat interface
- Implement all 5 GenUI components
- Wire render_component to frontend component router
- Build demo flow end to end
- Deploy Railway + Vercel

### Success criteria
- resolve_drug("Acetaminophen 500mg") returns correct Drug nodes
- Supply chain graph renders with manufacturer nodes and compliance flags
- Matching engine returns ranked list with explainable score breakdown
- At least one shortage or compliance risk surfaces without manual prompting
- Disambiguation works correctly for ambiguous drug names
- All 5 GenUI components render with real data

---

## Demo Flow

```
Query 1: "Show me the supply chain for Acetaminophen"
  resolve_drug -> get_supply_chain -> get_compliance_status for each manufacturer
  render supply_chain_graph
  2 manufacturer nodes red (FDA import alerts)
  User clicks red node -> compliance detail: firm, alert type, date, source link

Query 2: "Is Acetaminophen at risk of shortage?"
  check_shortage -> get_compliance_status
  render risk_card
  "Active shortage as of [date]. Reason: Manufacturing delay. 2 of 6 manufacturers flagged."

Query 3: "Find me a supplier to deliver 10,000 units to Chicago in 2 weeks"
  check_shortage -> match_suppliers -> find_alternatives (shortage active)
  render supplier_table
  Top match: Cardinal Health, score 0.89, clean, licensed in IL
  Alternatives: "If unavailable: Ibuprofen 400mg (therapeutic equivalent) — 3 clean suppliers"

Query 4: "Who are the distributors in Texas?"
  get_distributor_coverage("TX")
  render map_view
  12 distributors pinned in Texas, colour-coded by compliance
```

---

## References

- openFDA API: open.fda.gov/apis
- NDC Directory: open.fda.gov/data/ndc
- DECRS: catalog.data.gov — "Drug Establishments Current Registration Site"
- DSCSA distributor reporting: fda.gov/drugs/drug-supply-chain-security-act-dscsa
- Orange Book: fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files
- openFDA drug shortages: open.fda.gov/apis/drug/drugshortages
- FDA import alerts: fda.gov/safety/import-alerts
- Drugs@FDA data files: fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files