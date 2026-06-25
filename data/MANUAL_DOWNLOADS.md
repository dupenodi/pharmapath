# Manual datasets (downloaded — now ingested)

`fda.gov` blocks scripted requests (Akamai bot wall) and DECRS/DSCSA are
interactive tools rather than flat files, so these were downloaded by hand and
dropped into `data/raw/`. All four sources below are now parsed and built into
the graph at startup (`app/graph/store.py`). They are gitignored (regenerable
by re-downloading), so keep the originals if you wipe `data/raw/`.

| Source | Path in repo | Parser | Builds |
|---|---|---|---|
| NDC directory (openFDA bulk) | `data/raw/drug-ndc-0001-of-0001.json` | `app/ingestion/ndc.py` | Drug, Manufacturer, ActiveIngredient |
| Orange Book products | `data/raw/orange_book/products.txt` | `app/ingestion/orange_book.py` | therapeutic-equivalence enrichment on Drug |
| DECRS establishments | `data/raw/decrs/drls_reg.csv` | `app/ingestion/decrs.py` | Facility (+ authoritative repackager flag) |
| DSCSA wholesale/3PL | `data/raw/dscsa/<STATE>.csv` (52 files) | `app/ingestion/distributors.py` | Distributor + per-state licensing |

## Re-downloading if needed

- **Orange Book**: https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files
  → "Data Files" ZIP → unzip `products.txt` into `data/raw/orange_book/`.
- **DECRS**: https://www.fda.gov/drugs/drug-approvals-and-databases/drug-establishments-current-registration-site-decrs
  → export the `drls_reg` table as CSV → `data/raw/decrs/drls_reg.csv`.
  Columns used: `FEI_NUMBER, FIRM_NAME, ADDRESS, OPERATIONS, EXPIRATION_DATE, REGISTRANT_NAME`.
  Repackager = OPERATIONS has REPACK/RELABEL but not (API) MANUFACTURE.
- **DSCSA**: https://www.accessdata.fda.gov/scripts/cder/wdd3plreporting/index.cfm
  → export per state into `data/raw/dscsa/<STATE>.csv`.
  Columns used: `Facility Name, Facility Type (WDD|3PL), License Number, License State (US-XX)`.

## Known gap (not in any dataset)

There is still **no edge linking a Drug/Manufacturer to a Distributor** — no public
dataset says which distributor carries which SKU. The graph connects them indirectly
through Geography (Distributor→LICENSED_IN→Geography←LOCATED_IN←Facility←OPERATES←Manufacturer),
so sourcing should match a drug's manufacturer/state to distributors licensed in the
delivery state at query time rather than via a stored edge.
