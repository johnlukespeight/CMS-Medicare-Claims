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
orchestration/airflow/     Airflow DAGs                          [Milestone 1]
spark_jobs/                PySpark bronze/silver transforms      [Milestone 2]
dbt/medicare_claims/       dbt staging/intermediate/mart models  [Milestone 4]
dashboards/power_bi/       Power BI executive dashboard          [Milestone 6]
streamlit_app/             Streamlit exploration app             [Milestone 7]
```

## Getting started

```bash
make setup          # create .venv, install dev tooling
cp .env.example .env  # fill in cloud credentials as later milestones need them
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

Other `make` targets (`spark-test`, `dbt-build`, `streamlit-run`,
`airflow-up`) are stubbed until their milestone lands — see
[`docs/IMPLEMENTATION_SPEC.md` §28](docs/IMPLEMENTATION_SPEC.md) for the
full milestone list and current progress.

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

**Milestone 1 — Airflow Ingestion: mostly done, one step pending your GCP credentials.**

- [x] Local Airflow via Docker Compose (`make airflow-up`) — webserver at
      [localhost:8081](http://localhost:8081) (`admin`/`admin`), pinned to a
      non-default port/project name so it doesn't collide with any other
      local Airflow stack
- [x] `dag_ingest_beneficiary_raw`: `validate_raw_csv` → `land_raw_file` →
      `load_to_bigquery_task`, with the validation/manifest logic factored
      into `orchestration/airflow/dags/lib/beneficiary_ingest.py` and
      unit-tested (`make ingest-test`)
- [x] Ran end to end against the real 116,352-row file: validation and
      landing (checksum manifest) both succeed; the BigQuery load task fails
      cleanly with an actionable message since no GCP project is configured
      yet
- [ ] **Needs a GCP sandbox project** — add `GCP_PROJECT_ID` and
      `GOOGLE_APPLICATION_CREDENTIALS` (service-account JSON dropped in
      `secrets/`, gitignored) to `.env`, then re-trigger the DAG to complete
      the `medicare_raw.beneficiary_summary` load

Next: finish Milestone 1's BigQuery load once GCP credentials are available,
then **Milestone 2 — PySpark Bronze/Silver** (see spec §28).
