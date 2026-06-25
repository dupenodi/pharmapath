# EaseMed POC — Handoff & Review

**What this is:** a proof-of-concept built to show how I approach an ambiguous
problem ("pharma supply chain intelligence") end to end — real data, a graph,
a matching engine, an LLM agent over tools, and a UI — not a finished product.
This doc covers how to run and test it, what's actually in it, where I
deliberately cut scope and why, what I'd change to make it a real product, and
suggested next steps (email + hosting).

See `PLAN.md` for the original design doc this was built against.

---

## 1. How to test it

### 1.1 Setup (one-time)

```bash
# Backend
cd backend
cp .env.example .env        # fill in at least one LLM key (see below) + AGENT_PROVIDER
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
cp .env.example .env.local  # NEXT_PUBLIC_API_URL=http://localhost:8000 (MAPBOX_TOKEN optional)
npm install
npm run dev
```

The first backend start downloads/parses the public FDA bulk files (NDC,
Orange Book, DECRS, DSCSA) and builds the in-memory graph — takes a few
seconds once the raw files are cached locally (`data/raw/`, ~280MB, gitignored
and regenerated automatically).

`AGENT_PROVIDER` in `backend/.env` picks which LLM drives the chat agent —
`anthropic`, `gemini`, or `openai`. All three share the same tools, system
prompt, and UI contract, so any one of them is enough to test the full flow.
Only fill in the key for whichever you pick.

Frontend runs at `http://localhost:3000`. There are two surfaces:

- **`/` — Assistant**: chat interface. Ask it a procurement question; it
  calls tools and renders a UI component (supplier table, risk card, map,
  disambiguation prompt, etc.) alongside its text answer.
- **`/graph` — Supply Map**: a self-serve explorer. Search any drug,
  ingredient, manufacturer, or distributor and browse the graph directly —
  no LLM in the loop, this is pure data browsing.

### 1.2 Automated checks

```bash
cd backend && uv run pytest -q          # 105 tests — ingestion, graph build, matching, agent tools
cd frontend && npx tsc --noEmit         # typecheck
cd frontend && npx eslint .             # lint
```

These cover ingestion correctness, graph construction, the matching/scoring
logic, and the agent tool layer. They do **not** cover the LLM's own behavior
(tool choice, prose quality) — that needs manual testing, since it's
non-deterministic by nature.

### 1.3 Manual test script

**Supply Map (`/graph`) — no LLM, fastest way to sanity-check the data:**
1. Click an example chip (e.g. "Atorvastatin") — should land on a real drug
   record with NDC, FDA application number, manufacturer, and therapeutic
   equivalents, not a generic ingredient page.
2. Search a typo, e.g. `atorvastin` — should still find Atorvastatin
   (fuzzy fallback), with a "no exact match" note.
3. Search an OTC product, e.g. `tylenol` or `advil` — should resolve (OTC
   drugs are in the graph, not just Rx).
4. Click through a manufacturer or distributor node — check the
   relationship groups (made by, distributed by, licensed in) read sensibly.

**Assistant (`/`) — exercises the agent + tools + GenUI:**
1. `"I need acetaminophen for delivery to Illinois, are there any
   shortages?"` — should resolve the drug, check shortage, and either ask to
   narrow down (multiple strengths/forms exist) or run matching directly.
2. If asked to disambiguate, reply with the option you want (by name or by
   the `drug_id` it showed you) — should proceed without re-resolving.
3. Confirm the response includes: a supplier table or risk card, compliance
   status per supplier (clean/flagged/unknown — never silently assumed
   clean), and an explicit shortage check.
4. Ask about a drug + state combo you haven't asked about before, then ask
   again — the second answer should return noticeably faster (response
   cache on the live openFDA calls).
5. Try something deliberately ambiguous or malformed (a misspelled drug, a
   vague location) — it should ask a clarifying question rather than
   guessing.

**What "good" looks like:** every supplier surfaced has a compliance status
(never blank/assumed), every shortage/compliance claim is something the
tools actually returned (not invented), and capped lists (suppliers,
alternatives, distributors) say so explicitly rather than silently truncating.

---

## 2. What's actually built

| Layer | What it is |
|---|---|
| **Data** | 4 real FDA public datasets ingested and normalized: NDC (drug products), Orange Book (therapeutic equivalence), DECRS (manufacturing facility registrations), DSCSA (licensed wholesale distributors). No synthetic/fake data. |
| **Graph** | In-memory `networkx` graph, built fresh at backend startup. **134,196 nodes / 331,110 edges**: ~111k Drug (split roughly evenly Rx/OTC), ~6.3k ActiveIngredient, ~5.7k Manufacturer, ~9.9k Facility, ~1.4k Distributor, 51 Geography (states + DC). |
| **Live enrichment** | Compliance flags and active shortages are fetched live from openFDA per query (not pre-ingested), with a 1-hour response cache. |
| **Matching engine** | Structured procurement request → scored, ranked supplier list. Four weighted dimensions (compliance, availability, location, coverage), hard disqualifiers (not licensed in state, active Class I-equivalent recall), an urgency weighting shift for short deadlines. |
| **Agent** | LLM-driven (swappable: Anthropic/Gemini/OpenAI) tool-calling loop, 8 tools shared across all three providers, with a server-side fallback that synthesizes the UI component if a model answers correctly but forgets to call `render_component`. |
| **Frontend** | Next.js + React 19 + Tailwind. Two surfaces: a chat Assistant with generative UI, and a self-serve Supply Map graph explorer (Cytoscape) with full-text/fuzzy search. |

### Iteration history (the part that's hard to see from the code alone)

This wasn't built once — it went through real review/fix cycles, each found
by actually using the thing, not just reading the code:

1. **Data layer build** — ingested and normalized the 4 sources, deduped NDC
   records, fuzzy-matched manufacturer names across datasets (DECRS/NDC/DSCSA
   spell company names inconsistently).
2. **Graph connectivity audit** — found the graph was effectively two
   disconnected halves (drug↔manufacturer and distributor↔geography never
   linked) until Manufacturer↔Facility↔Geography edges were added from DECRS.
3. **UX testing pass** — used the Supply Map as a real user would and found:
   a facility-match bug that left 69 manufacturers on a weaker unconfirmed
   heuristic, a "24 of 335" truncation that was silently lying about totals,
   no fuzzy/typo tolerance in search, OTC drugs entirely invisible (same
   error as a typo or nonexistent drug), onboarding example chips always
   landing on a generic ingredient hub instead of a real product, and a
   genuine CSS rendering bug (dropdown overlapping UI chips).
4. **Agent tools rewrite** — the tools/system prompt predated the data
   rebuild and made false claims about their own limits (e.g. "Orange Book
   not ingested" when it had been for a while). Live testing (not just unit
   tests) found a real performance bug — the matching engine was firing a
   live HTTP compliance check against every one of 1,356 distributors per
   query, ~1,300 of them pointless — and a fuzzy-matching bug where a messy
   query produced 1,880 garbage drug matches. Both fixed and verified against
   the full dataset, not just small test fixtures.

I'm calling this out specifically because **"did you test what you built, or
just read the code and assume it works"** is, I think, exactly the kind of
thing this assignment is trying to surface.

---

## 3. Where I deliberately limited scope (and why)

Every limit below was a deliberate call to keep the POC buildable in the
time available, not an oversight. They're documented in `PLAN.md` and in
code comments at the exact place they apply.

| Limit | Why | What it would take to lift |
|---|---|---|
| **No drug → distributor link.** Distributor candidates are inferred from *state license coverage* only, never "this distributor actually carries this drug." | No public dataset links the two — DSCSA licenses are state-level, not product-level. | This is a real data gap, not an engineering one. Would need a commercial data source (e.g. a GPO/wholesaler relationship feed) or direct distributor partnerships. |
| **Distributor entity fragmentation.** DSCSA licenses some companies (McKesson, specifically) warehouse-by-warehouse, so one real company can appear as ~34 near-duplicate entities. | Public data artifact, not a bug in the ingestion logic. | Needs an entity-resolution pass (cluster by parent-company name) — a deliberate product decision about what "one distributor" means, not just a fix. |
| **Compliance is firm-level, not facility-level.** openFDA enforcement data only resolves to a company name. | openFDA's own data granularity. | Would need a different/paid compliance data source with facility-level resolution. |
| **In-memory graph, rebuilt from scratch on every restart.** No persistence, no incremental updates, no versioning/audit trail. | Fine for a single-process POC; a real backing store is a different infrastructure decision than "is the graph schema right." | Swap to a real graph DB (Neo4j) or a relational store with a graph layer, with a scheduled ingestion pipeline instead of build-on-startup. |
| **No auth, no multi-tenancy, no rate limiting on the agent endpoint.** Chat history is a single global in-memory dict keyed by session ID. | Out of scope per `PLAN.md` — this proves the intelligence layer works, not the SaaS shell around it. | Standard: real auth (Clerk/Auth0/etc.), per-org data scoping if multiple hospital systems use it, a real session store (Redis/Postgres). |
| **US-only, FDA-regulated drugs only.** No biologics, devices, or other countries' regulatory data. | Scoping decision in `PLAN.md` to keep the data model tractable. | Each is a real, separate ingestion + schema effort (e.g. India's CDSCO has a completely different data shape). |
| **Agent latency: 5-45s per turn** depending on how many tool calls a request needs. | Inherent to multi-step LLM tool-calling against a non-trivial dataset; verified the *tools themselves* run in ~0.01-12s (cache-dependent) — the remaining time is sequential LLM round-trips. | Parallel tool calling (where the model's API supports it), a faster/cheaper model for simple turns, or streaming partial results to the UI while later tool calls are still running. |
| **No production-grade data refresh.** The graph is built once at startup from whatever's in `data/raw/`; there's no scheduled re-ingestion job. | Explicitly out of scope per `PLAN.md` (item: "production-grade data pipelines or scheduled refresh"). | A real job scheduler (Airflow/Dagster/cron) re-pulling FDA sources on their actual publish cadence, with diffing/alerting on schema drift. |

---

## 4. If this became a real product — what I'd change

Roughly in the order I'd actually tackle them:

1. **Persistent, queryable data store.** Move off in-memory `networkx` to a
   real graph database (Neo4j is the natural fit given the schema) or at
   minimum a relational store with proper indexes. This unlocks horizontal
   scaling, faster cold starts, and incremental updates instead of full
   rebuilds.
2. **A real ingestion pipeline**, not a startup-time script: scheduled pulls
   from FDA sources, diffing against the previous graph, alerting on schema
   changes (these are public bulk files that do occasionally change shape),
   and a way to roll back a bad ingest.
3. **Solve the drug→distributor gap properly.** This is the single biggest
   product credibility risk — right now "who can supply this" is inferred
   from state licensing, not actual product carriage. Needs either a
   commercial data partnership or a different sourcing model (e.g. RFQ-based,
   where distributors self-report what they stock).
4. **Entity resolution as a first-class system**, not a one-off fuzzy-match
   pass — the McKesson-fragmentation problem will recur with every new data
   source. A proper entity-resolution/dedup layer (with human review for
   uncertain merges) pays for itself fast.
5. **Auth, multi-tenancy, audit logging.** Procurement decisions for a
   hospital are exactly the kind of thing that needs an audit trail (who
   asked what, what the system said, what they did with it) — both for trust
   and for liability reasons given this touches health-system purchasing.
6. **Agent observability and eval harness.** Right now correctness is
   verified by hand (exactly the testing I did this session). A real product
   needs: traced tool calls per request, a golden-set of procurement
   scenarios with expected tool sequences/outputs, and regression detection
   when a model or prompt change silently breaks behavior.
7. **Cost and latency controls for the LLM layer.** Track $ and latency per
   conversation, set a budget/timeout policy, and consider a cheaper/faster
   model for simple lookups vs. a stronger one only when matching/scoring
   is actually involved.
8. **Compliance/legal review specific to healthcare procurement.** This
   system would be influencing real purchasing decisions for hospitals
   sourcing drugs. Before any real customer use, there should be an explicit
   disclaimer/liability framework around the data (e.g. "this is not a
   substitute for direct verification with the supplier") — the agent
   already refuses to guess (no inventory claims, no assumed-clean
   compliance), but that intent should be backed by an actual policy, not
   just the system prompt.
9. **CI/CD.** Right now tests are run by hand. A real product needs GitHub
   Actions (or similar) running `pytest`/`tsc`/`eslint` on every PR, plus a
   staging environment that mirrors production data scale.

---

## 5. Next steps (for you)

**Email to the founder** — short draft you can adapt:

> Subject: EaseMed POC — repo + demo
>
> Hi [Nikita/founder name],
>
> Here's the POC: [GitHub link]. I've also recorded a short demo walking
> through both surfaces (chat assistant + the supply map explorer) — [link].
>
> Quick summary: it ingests 4 real FDA datasets into a ~134k-node knowledge
> graph, runs a procurement-matching engine over it, and exposes both a
> self-serve explorer and an LLM agent that calls tools over the graph. I've
> also put together a short write-up of what's in scope, what I deliberately
> left out and why, and what I'd do differently for a real product — happy
> to walk through it live.
>
> [Your name]

**GitHub:** repo is already at `https://github.com/dupenodi/pharmapath` (per
`git remote -v`) — confirm it's set to the visibility you want before
sending the link (public vs. inviting the founder as a collaborator on a
private repo).

**Demo recording:** record both surfaces — a couple of Supply Map searches,
then a full Assistant conversation (drug → disambiguation → shortage check →
supplier table), so the founder sees the agent reasoning, not just a single
search bar.

**Hosting — backend on Render, frontend on Vercel (both free):**

A real constraint to know about: the full dataset (Rx + OTC) peaks at
~670MB RAM during the one-time startup graph build, over Render's free
512MB cap. Fixed two ways — streaming the 244MB NDC parse instead of
loading it all into memory at once (cut peak from ~1.4GB to ~670MB), and a
`GRAPH_SCOPE=rx_only` setting that drops OTC drugs and brings it to ~370MB,
comfortably inside the free tier. `render.yaml` at the repo root already
sets this for you.

1. **Backend (Render):**
   - On [render.com](https://render.com), "New" → "Blueprint" → connect the
     `dupenodi/pharmapath` GitHub repo. It reads `render.yaml` and
     pre-fills everything (free plan, build/start commands, `rootDir:
     backend`, `GRAPH_SCOPE=rx_only`).
   - You'll be prompted for `OPENAI_API_KEY` (marked secret in the
     blueprint, so it's never committed) — paste your key. `render.yaml` is
     set to `AGENT_PROVIDER=openai`/`gpt-4o`; swap those env vars if you'd
     rather use Anthropic or Gemini instead.
   - Deploy. First boot downloads the NDC file and builds the graph — give
     it a minute or two. Check `https://<your-service>.onrender.com/health`
     returns `"graph_loaded": true`.
   - Free-tier services sleep after 15 min idle and take ~30-60s to wake on
     the next request — normal, not a bug, if the first demo request after
     a pause feels slow.
2. **Frontend (Vercel):**
   - On [vercel.com](https://vercel.com), "New Project" → import the same
     repo → set **Root Directory** to `frontend` (the dashboard setting,
     not a config file — this is a monorepo with the backend alongside it).
   - Set env vars: `NEXT_PUBLIC_API_URL` = your Render backend URL from
     step 1; `NEXT_PUBLIC_MAPBOX_TOKEN` is optional (the map view falls
     back to a plain list without it).
   - Deploy.
3. **Connect them:** once you have the Vercel URL, go back to the Render
   service's env vars and set `CORS_ORIGINS` to
   `["https://<your-app>.vercel.app"]` (replacing the localhost placeholder
   in `render.yaml`) and redeploy the backend so it accepts requests from
   the live frontend.

I haven't created any accounts, deployed anything, or sent the email —
wanted to leave those as explicit calls for you to make (recipient, repo visibility,
whether you want it hosted before sending).
