# Manual downloads needed for Phase 1

`fda.gov` blocks scripted requests (Akamai bot wall), and DECRS/DSCSA are
interactive search tools rather than flat files, so these three need to be
downloaded by hand in a browser and dropped into this directory. NDC is
already done (downloaded live, see `drug-ndc-0001-of-0001.json`).

## 1. Orange Book

1. Open https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files
2. Download the "Data Files" ZIP (contains `products.txt`, `patent.txt`, `exclusivity.txt`, tilde-delimited).
3. Unzip it into `data/raw/orange_book/` so the files are at:
   - `data/raw/orange_book/products.txt`
   - `data/raw/orange_book/patent.txt`
   - `data/raw/orange_book/exclusivity.txt`

## 2. DECRS (Drug Establishments Current Registration Site)

1. Open https://www.fda.gov/drugs/drug-approvals-and-databases/drug-establishments-current-registration-site-decrs
   (or the HealthData.gov mirror at https://healthdata.gov/dataset/Drug-Establishments-Current-Registration-Site/s52i-rmqw)
2. Export/download the full dataset as CSV.
3. Save it as `data/raw/decrs.csv`.

## 3. DSCSA wholesale distributor / 3PL annual reporting database

1. Open https://www.accessdata.fda.gov/scripts/cder/wdd3plreporting/index.cfm
2. Run a search that returns all records (or per the big-3-only Phase 1 scope:
   McKesson, Cardinal Health, AmerisourceBergen/Cencora and their licensed
   subsidiaries — see `app.core.config.settings.big3_distributor_names`).
3. Export the results as CSV and save as `data/raw/dscsa_distributors.csv`.

Once these three files exist at the paths above, ping me to resume ingestion —
the Orange Book parser is already written against the real tilde-delimited
format; DECRS/DSCSA parsers will be finalized once I can see the actual
column headers from your exports (government CSV exports vary).
