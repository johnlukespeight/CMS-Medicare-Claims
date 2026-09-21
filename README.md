# Medicare Claims Analytics Platform

A data engineering portfolio project built on the public **CMS DE-SynPUF**
2008 Beneficiary Summary File (Sample 1, 116,352 synthetic beneficiaries) to
get real, demonstrable, interview-ready depth with: **Apache Airflow**,
**dbt**, **PySpark**, **Databricks SQL / Unity Catalog**, **BigQuery**,
**Looker Studio**, and **Streamlit**.

The data is entirely synthetic and public — see [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md).
It is not real patient data.

## Architecture

One raw landing zone feeds two parallel processing paths, orchestrated by a
single Airflow instance, surfaced through two BI layers:

```
                         ┌──────────────────────────┐
                         │   Airflow orchestrates    │
                         │   every arrow below        │
                         └──────────────────────────┘
Raw CSV (CMS DE-SynPUF)
        │
        ├──► PySpark ──► Databricks Unity Catalog        ──► Looker Studio
        │    (bronze → silver → gold, Delta)                  (executive
        │                                                       dashboard)
        └──► BigQuery raw ──► dbt (staging → marts)       ──► Streamlit
                                                                (ad hoc
                                                                 exploration)
```

See [`docs/IMPLEMENTATION_SPEC.md`](docs/IMPLEMENTATION_SPEC.md) for the
full architecture, data model, and milestone-by-milestone build plan, and
[`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) for why
it's shaped this way.

## Repository layout

```
CLAUDE.md / AGENTS.md      Coding-agent entrypoints (hard constraints, milestone order)
PRODUCT_SPEC.md            Why this project exists, portfolio framing
docs/                      Implementation spec, ADR log, data governance
data/raw/                  Raw CMS DE-SynPUF file (gitignored — not committed)
data/samples/              Small committed fixture sample for tests/local dev
notebooks/                 Data profiling
scripts/                   One-off utilities (sample generation, notebook build)
orchestration/airflow/     Airflow DAGs                          [Milestone 1, 3]
spark_jobs/                PySpark bronze/silver transforms      [Milestone 2]
spark_jobs/databricks/     Databricks notebook/SQL + deploy script [Milestone 3]
dbt/medicare_claims/       dbt staging/intermediate/mart models  [Milestone 4]
dashboards/looker_studio/  Looker Studio executive dashboard (URL + build spec) [Milestone 6]
streamlit_app/             Streamlit exploration app             [Milestone 7]
```

## Getting started

```bash
make setup          # create .venv, install dev tooling
cp .env.example .env  # fill in cloud credentials as later milestones need them
```

PySpark work (`spark_jobs/`) needs its own venv — as of this writing PySpark
requires Python <=3.13 and Java 8/11/17, which may not match your default
`python3`:

```bash
brew install openjdk@17   # if you don't already have a Java 8/11/17
make setup-spark          # creates .venv-spark on python3.13
make spark-test           # unit tests
make spark-run            # runs the bronze/silver job against the fixture sample
```

The raw file is already in `data/raw/` (gitignored). To regenerate the
committed fixture sample used by tests and local dev:

```bash
make sample-data
```

To re-run the data profiling notebook against the full raw file:

```bash
make profile
```

dbt (`dbt/medicare_claims/`) runs against the same BigQuery sandbox project
as the ingestion DAG — no extra cloud setup needed beyond the GCP section
below:

```bash
make dbt-seed    # loads the ssa_state_codes reference table
make dbt-build   # seed + staging/intermediate/marts models + all tests
make dbt-docs    # generate + serve the lineage graph at localhost:8082
```

`dag_dbt_transform` (Airflow) runs `dbt build` from a separate venv baked
into the Airflow image (`/opt/dbt-venv`) — see ADR-008 for why it's isolated
from Airflow's own Python environment.

```bash
make streamlit-test           # unit tests (DuckDB backend, no cloud needed)
make streamlit-run            # app at localhost:8501, STREAMLIT_BACKEND=duckdb against the fixture sample
make streamlit-run-bigquery   # same app against the live BigQuery sandbox project
```

See [`docs/IMPLEMENTATION_SPEC.md` §28](docs/IMPLEMENTATION_SPEC.md) for
the full milestone list and current progress.

### GCP sandbox setup (one-time, for the BigQuery path)

No billing account needed — BigQuery's free Sandbox mode (10GB storage /
1TB queries per month) covers this project easily:

```bash
gcloud projects create <your-project-id> --name="Medicare Claims Analytics"
gcloud services enable bigquery.googleapis.com --project=<your-project-id>

gcloud iam service-accounts create medicare-airflow \
  --project=<your-project-id> --display-name="Medicare Airflow Ingestion"

for ROLE in roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding <your-project-id> \
    --member="serviceAccount:medicare-airflow@<your-project-id>.iam.gserviceaccount.com" \
    --role="$ROLE" --condition=None
done

gcloud iam service-accounts keys create secrets/gcp-service-account.json \
  --iam-account=medicare-airflow@<your-project-id>.iam.gserviceaccount.com \
  --project=<your-project-id>
```

Then set `GCP_PROJECT_ID=<your-project-id>` in `.env` and `make airflow-up`
(or `docker compose up -d --force-recreate airflow-scheduler airflow-webserver`
if it's already running).

### Databricks setup (one-time, for the lakehouse path)

1. Sign up at `databricks.com/try-databricks` (choose **AWS** + **Express
   Setup** for a trial, or use **Databricks Free Edition** if it's offered —
   either way, no credit card needed and Unity Catalog is enabled by
   default). Free Edition ships **serverless-only** compute (no classic
   clusters) — see ADR-007 for what that changes about how the job ships.
2. In the workspace: **Catalog** → create a catalog named `medicare` (or
   let `deploy.py` find it — it doesn't create the catalog itself, only the
   `bronze`/`silver`/`gold` schemas and a `raw_files` volume inside it).
3. Generate a personal access token: avatar → **Settings** → **Developer**
   → **Access tokens** → **Generate new token**.
4. Set `DATABRICKS_HOST` (the workspace URL) and `DATABRICKS_TOKEN` in
   `.env`.
5. Deploy and run:

```bash
make databricks-deploy   # uploads transforms/notebook/gold SQL + raw CSV, creates the Job
make databricks-run      # deploy, then trigger it and wait for it to finish
```

`dag_spark_bronze_silver` (Airflow) only triggers/waits on the already-
deployed job — re-run `make databricks-deploy` whenever the transform logic
or gold SQL changes.

### Looker Studio setup (one-time, for the fixed dashboard)

Free, browser-based, no Windows/VM needed (see ADR-010 for why this
replaced Power BI). There's no CLI/API for authoring a report from
scratch, so this is a one-time manual step at
[lookerstudio.google.com](https://lookerstudio.google.com):

1. **Create** → **Report**. Add a BigQuery data source for each mart
   (`mart_state_cost_summary`, `mart_chronic_condition_prevalence`,
   `fct_beneficiary_annual_cost` joined to `dim_beneficiary`) — connect as
   the same Google account already used for the GCP sandbox project above.
2. Build the three pages exactly as specified in
   [`dashboards/looker_studio/README.md`](dashboards/looker_studio/README.md)
   (charts, fields, and filters for Overview / Chronic Conditions / Cost
   Mix).
3. **Share** → get the report's viewable link, and paste it into
   `dashboards/looker_studio/README.md`.

No cloud credentials to manage — the report authenticates as whichever
Google account is viewing/editing it.

## Status

**Milestone 0 — Repository Foundation: done.**

- [x] Repo layout, `.gitignore`, dev tooling (`make setup`)
- [x] Committed fixture sample (`data/samples/beneficiary_summary_sample.csv`,
      342 rows stratified across all 52 states plus every deceased
      beneficiary in the source file)
- [x] Data profiling notebook run against the full 116,352-row file,
      confirming the chronic-condition flag encoding, death-date null rate,
      and — notably — that `MEDREIMB_IP`/`MEDREIMB_OP` are not guaranteed
      non-negative (claim adjustments exist in the real data)

**Milestone 1 — Airflow Ingestion: done.**

- [x] Local Airflow via Docker Compose (`make airflow-up`) — webserver at
      [localhost:8081](http://localhost:8081) (`admin`/`admin`), pinned to a
      non-default port/project name so it doesn't collide with any other
      local Airflow stack
- [x] `dag_ingest_beneficiary_raw`: `validate_raw_csv` → `land_raw_file` →
      `load_to_bigquery_task`, with the validation/manifest logic factored
      into `orchestration/airflow/dags/lib/beneficiary_ingest.py` and
      unit-tested (`make ingest-test`)
- [x] GCP sandbox project `medicare-claims-de-synpuf` provisioned (no
      billing — BigQuery free Sandbox mode), with a scoped service account
      (`bigquery.dataEditor` + `bigquery.jobUser` only) whose key lives in
      `secrets/` (gitignored)
- [x] Ran end to end against the real 116,352-row file: `medicare_raw.beneficiary_summary`
      in BigQuery holds exactly 116,352 rows. Re-triggered a second time to
      confirm the full-refresh load is idempotent — row count stayed at
      116,352 both runs, no duplication.

**Milestone 2 — PySpark Bronze/Silver: done.**

- [x] `spark_jobs/transforms/beneficiary_transforms.py` — pure, testable
      bronze (type casting only) and silver (decoded chronic-condition
      flags, `age_2008`/`age_band`, `is_deceased`, SSA state-code lookup
      verified against the official CMS DE-SynPUF codebook, `chronic_condition_count`)
      transforms; 11 unit tests (`make spark-test`), including one asserting
      exact hand-checked values for a real beneficiary from the fixture file
- [x] `spark_jobs/jobs/beneficiary_bronze_silver.py` — runnable job, writes
      local Delta tables (`make spark-run`); verified against both the
      342-row fixture and the full 116,352-row raw file (bronze/silver row
      counts match exactly, no dedup loss)
- [x] Negative reimbursement values (§8's profiling finding) confirmed
      preserved unchanged through the transform, not clipped

**Milestone 3 — Databricks Unity Catalog: done.**

- [x] Unity Catalog `medicare` catalog with `bronze`/`silver`/`gold` schemas
      and a `bronze.raw_files` managed Volume holding the landed CSV
- [x] `spark_jobs/databricks/deploy.py` — idempotently uploads the *same*
      `beneficiary_transforms.py` from Milestone 2 (as a workspace file,
      not duplicated), the driver notebook, and the gold SQL, then
      creates/updates a persisted Databricks Job (`medicare_bronze_silver_gold`)
- [x] Gold layer as Databricks SQL: `gold.beneficiary_cost_summary` (one row
      per beneficiary) and `gold.chronic_condition_prevalence` (11
      conditions × 52 states = 572 rows, via `UNPIVOT`)
- [x] `dag_spark_bronze_silver` (Airflow) triggers the deployed job and
      polls it to completion — `orchestration/airflow/dags/lib/databricks_job.py`
      unit-tested (`make ingest-test`)
- [x] Ran end to end against the real 116,352-row file, via both
      `make databricks-run` and the live Airflow DAG: bronze/silver/gold row
      counts all match Milestone 2's local run exactly, and
      `gold.chronic_condition_prevalence`'s overall rates match
      `notebooks/00_data_profiling.ipynb`'s original findings exactly (e.g.
      ischemic heart disease 42.1%, diabetes 37.9%)
- Free Edition turned out to be **serverless-only** (no classic clusters) —
  see ADR-007 for how that changed the job's shape from what was originally
  planned

**Milestone 4 — BigQuery + dbt: done.**

- [x] `dbt/medicare_claims/`: `stg_beneficiary_summary` (staging) →
      `int_beneficiary_chronic_conditions` / `int_beneficiary_annual_cost`
      (intermediate) → `dim_beneficiary` / `fct_beneficiary_annual_cost` /
      `mart_chronic_condition_prevalence` / `mart_state_cost_summary`
      (marts) — the same decode/aggregation logic as Milestones 2-3,
      independently reimplemented in dbt SQL per ADR-001 (each path owns its
      own logic)
- [x] `ssa_state_codes` dbt **seed** (not a hardcoded `CASE WHEN`) — same
      CMS-codebook-verified data as `beneficiary_transforms.py`'s lookup
- [x] 42/42 `dbt build` tests pass, including `accepted_values` and a
      `relationships` foreign-key test from `fct_beneficiary_annual_cost` to
      `dim_beneficiary`; `dbt docs generate` produces a browsable lineage
      graph (`make dbt-docs`)
- [x] `dag_dbt_transform` (Airflow) runs `dbt build` from an isolated venv
      (`/opt/dbt-venv`) — installing dbt into Airflow's *own* environment
      produced ~30 real dependency conflicts (protobuf, pandas,
      opentelemetry), confirmed by actually trying it; see ADR-008
- [x] Ran end to end, both via `make dbt-build` and a live Airflow trigger:
      all marts land at exactly 116,352 rows (stg/dim/fct) and 583
      (`mart_chronic_condition_prevalence`, 11 conditions × 52 states + 11
      "All States" rows); prevalence rates match
      `notebooks/00_data_profiling.ipynb`'s original findings exactly (e.g.
      42.06% ischemic heart disease, 37.87% diabetes)

**Milestone 5 — Reconciliation: done.**

- [x] `dag_gold_reconcile`: fetches `COUNT(*)`/`SUM(total_medicare_reimbursement)`
      from Databricks `gold.beneficiary_cost_summary` (via the SQL
      Statement Execution API) and BigQuery `fct_beneficiary_annual_cost`
      (via the `google-cloud-bigquery` client) in parallel, then compares
      them — exact match on beneficiary count, $1 tolerance on the cost sum
      (defensive practice for cross-engine float summation, even though
      both report exactly $465,233,840.00 in practice)
- [x] **Verified both halves of the acceptance criteria for real**, not
      just by reasoning about the code: ran the DAG against the untouched
      pipeline (passed), used a Databricks SQL `UPDATE` to intentionally
      add $500 to one beneficiary's cost (BigQuery's free-tier Sandbox mode
      blocks DML entirely, so the deliberate mismatch had to go on the
      Databricks side), re-ran the DAG and watched it **fail with an exact,
      actionable diagnostic** (`total_medicare_reimbursement mismatch:
      Databricks=465234340.00 BigQuery=465233840.00 (diff=500.00,
      tolerance=1.0)`), then reverted via `make databricks-run`
      (full-refresh) and confirmed the DAG passes again

**Milestone 6 — Looker Studio Dashboard: in progress.**

Originally scoped around Power BI; replaced with **Looker Studio** per
ADR-010 — free, browser-based, BigQuery-native, no Windows/VM needed
(Power BI Desktop is Windows-only; this project is built on macOS).
Milestone 7 was built first while this was blocked, then unblocked once the
tool swap was decided. Build spec and report URL live in
[`dashboards/looker_studio/README.md`](dashboards/looker_studio/README.md).

**Milestone 7 — Streamlit Exploration App: done.**

- [x] `streamlit_app/data_access.py` — one interface, two backends
      (`STREAMLIT_BACKEND=duckdb` for zero-cost local dev against the
      fixture sample, `=bigquery` against the live sandbox), both returning
      the identical per-beneficiary shape so `app.py` filters/aggregates
      once regardless of backend
- [x] BigQuery backend joins `dim_beneficiary`/`fct_beneficiary_annual_cost`
      (marts) with `stg_beneficiary_summary` (staging) for per-beneficiary
      condition flags — no mart carries those at the right grain for the
      app's cross-filters; a narrow, documented boundary crossing (ADR-009)
- [x] Sidebar filters (state, age band, *any of* 11 chronic conditions,
      deceased/alive) drive three views: a by-state summary table, a cost
      distribution histogram, and a condition-prevalence bar chart
- [x] 7 unit tests, including one that cross-checks a DuckDB-backend row
      against hand-computed values from the raw fixture CSV directly (no
      hardcoded expectations to go stale)
- [x] **Verified with a real headless-Chromium/Playwright session**, not
      just unit tests or a curl smoke test: launched the app, applied
      filters through actual sidebar UI interactions, confirmed the
      beneficiary count cascaded correctly (342 → 7 with a state filter →
      1 with a deceased filter on top), zero browser console errors, and
      confirmed the BigQuery backend's numbers match Milestone 5's
      reconciled totals exactly ($465,233,840 total cost; state-by-state
      counts matching the original profiling notebook)

Next: building out **Milestone 6 — Looker Studio Dashboard**, then
**Milestone 8 — Integrated Demo & Hardening** (see spec §28).
