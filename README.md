# EaseMed POC

Pharma supply chain intelligence platform proof-of-concept. See `PLAN.md` for the
full design (data sources, knowledge graph schema, matching engine, agent, GenUI)
and the approved implementation plan for the phase sequence this repo follows.

## Layout

- `backend/` — FastAPI service: graph store, ingestion, matching engine, agent, API
- `frontend/` — Next.js app: chat UI + GenUI components
- `data/raw/` — downloaded FDA source files (gitignored, regenerable)
- `data/cache/` — geocoding/openFDA caches (gitignored, regenerable)

## Backend

```
cd backend
cp .env.example .env   # fill in ANTHROPIC_API_KEY
uv run uvicorn app.main:app --reload
uv run pytest
```

Health check: `curl http://localhost:8000/health`

## Frontend

```
cd frontend
cp .env.example .env.local   # fill in MAPBOX_TOKEN
npm run dev
```

Serves at http://localhost:3000, calls the backend at `NEXT_PUBLIC_API_URL`.
