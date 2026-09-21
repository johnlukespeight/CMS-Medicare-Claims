# Medicare Claims Analytics Platform

A data engineering portfolio project built on the public **CMS DE-SynPUF**
2008 Beneficiary Summary File (Sample 1, 116,352 synthetic beneficiaries) to
get real, demonstrable, interview-ready depth with: **Apache Airflow**,
**dbt**, **PySpark**, **Databricks SQL / Unity Catalog**, **BigQuery**,
**Power BI**, and **Streamlit**.

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
        ├──► PySpark ──► Databricks Unity Catalog        ──► Power BI
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
dashboards/power_bi/       Power BI executive dashboard          [Milestone 6]
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

Other `make` targets (`dbt-build`, `streamlit-run`) are stubbed until their
milestone lands — see
[`docs/IMPLEMENTATION_SPEC.md` §28](docs/IMPLEMENTATION_SPEC.md) for the
full milestone list and current progress.

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

Next: **Milestone 4 — BigQuery + dbt** (see spec §28).
