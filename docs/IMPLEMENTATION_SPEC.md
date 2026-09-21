# Medicare Claims Analytics Platform — Coding Agent Implementation Specification

**Document purpose:** Source-of-truth implementation brief for Claude Code / any coding agent working in this repo
**Project:** Medicare Claims Analytics Platform (CMS DE-SynPUF)
**Stage:** Portfolio / interview-preparation build — treat milestones like production increments even though there's no external user
**Primary language(s):** Python (PySpark, Airflow, Streamlit), SQL (dbt, BigQuery, Databricks SQL)
**Architecture style:** Two parallel processing paths off one raw landing zone — lakehouse (Databricks/Unity Catalog) and warehouse ELT (BigQuery/dbt) — unified by a single Airflow orchestrator and two BI surfaces
**Deployment target:** Local (Docker Compose Airflow, local Spark, DuckDB) → cloud sandbox (Databricks free/Community workspace, BigQuery sandbox project, Looker Studio — free, browser-based)
**Guiding principle:** Prefer the simplest design that gives every tool in the required list — Airflow, dbt, PySpark, Databricks/Unity Catalog, BigQuery, Looker Studio, Streamlit — a real, idiomatic role, over a design that makes any one of them decorative.

---

# 0. Instructions to the Coding Agent

Treat this document as the primary engineering specification unless a newer
human-authored decision explicitly overrides it.

## Working rules

1. Build milestones in order (§28). Do not start the Databricks/Spark layer
   before the Airflow ingestion DAG lands raw data; do not start dbt before
   raw data is loaded into BigQuery; do not start Looker Studio/Streamlit
   before at least one gold mart exists to point them at.
2. Every schema (bronze/silver/gold Delta tables, BigQuery staging/mart
   models) is defined once, in code, and reused — never redefined ad hoc in
   a notebook, dashboard, or Streamlit query.
3. All chronic-condition flag decoding (`1=Yes`, `2=No` per the CMS DE-SynPUF
   codebook) and reimbursement aggregation logic lives in the PySpark
   silver job and/or dbt staging models — never recomputed differently in
   two places.
4. Every Airflow DAG, Spark job, and dbt model must be idempotent: re-running
   it against the same raw file produces the same output, never duplicate
   rows.
5. Only the CMS DE-SynPUF Beneficiary Summary file (Sample 1) is in scope.
   See `docs/GOVERNANCE.md` and §35 for what's explicitly deferred.
6. Add tests alongside every feature — PySpark unit tests for transformation
   functions, dbt tests for every staging/mart model.

## Definition of a good implementation

A milestone is done when: its Airflow DAG (if any) runs green end to end
locally, its tests pass, its output table/dashboard is inspectable and
matches the acceptance criteria in §28, and any schema or architecture
decision it introduced is recorded in `docs/ARCHITECTURE_DECISIONS.md`.

# 1. Product Definition

A self-contained data engineering portfolio project that ingests the public
CMS DE-SynPUF 2008 Beneficiary Summary File and turns it into two governed
analytical layers — a Databricks/Unity Catalog lakehouse and a BigQuery/dbt
warehouse — orchestrated end to end by Airflow, and exposed through two BI
surfaces (Looker Studio for fixed reporting, Streamlit for ad hoc exploration).
It exists to give hands-on, demonstrable, interview-ready experience with
each required tool used the way it's actually used in industry, not as a
disconnected tutorial exercise.

# 2. Portfolio-Build User Story

A visitor (recruiter, hiring manager, or the developer in an interview)
opens the Streamlit app or the Looker Studio dashboard and sees: how many
Medicare beneficiaries are enrolled by state, the prevalence of each of the
11 tracked chronic conditions, and how inpatient/outpatient/carrier
reimbursement is distributed across beneficiaries and conditions. Behind
that dashboard, the developer can walk an interviewer through: the Airflow
UI showing the DAG that landed the raw CSV and triggered downstream jobs;
the Databricks Unity Catalog explorer showing bronze/silver/gold Delta
tables with lineage; and the dbt docs site showing the staging → marts DAG
with tests passing in BigQuery.

# 3. Explicit Non-Goals

- Real-time/streaming ingestion (data is a static annual file — batch only).
- Ingesting the DE-SynPUF Inpatient/Outpatient/Carrier Claims or PDE files
  (deferred, see §35).
- Real Medicare data, PHI, or PII of any kind.
- Multi-user authentication/authorization beyond default cloud IAM and
  Streamlit's basic auth (if any).
- Kubernetes, Kafka/streaming infra, or a second orchestrator.
- Productionized ML (an optional cost-prediction notebook is a stretch goal
  only — see §35 — never a core deliverable).

# 4. Architecture Decision Summary

## Initial stack

| Concern | Choice |
|---|---|
| Orchestration | Apache Airflow (local, Docker Compose) |
| Lakehouse processing | PySpark jobs on Databricks |
| Lakehouse governance | Databricks Unity Catalog (`medicare.bronze/silver/gold`) |
| Warehouse | Google BigQuery (sandbox project) |
| Warehouse transformation | dbt-core (dbt-bigquery adapter) |
| Fixed BI dashboard | Looker Studio (native BigQuery connector) |
| Ad hoc exploration app | Streamlit (BigQuery + local DuckDB fallback) |
| Local dev warehouse stand-in | DuckDB (for Streamlit/dbt iteration without cloud cost) |

## Why not [more complex alternative] now?

- **No streaming (Kafka/Kinesis):** the source is a static annual CMS
  release; batch orchestration is the realistic and interview-relevant
  pattern here.
- **No Great Expectations/Soda:** dbt's built-in schema tests
  (`not_null`, `unique`, `accepted_values`, `relationships`) plus PySpark
  unit tests cover this project's data-quality surface without a second DQ
  framework.
- **No dbt Cloud / Databricks Workflows as the orchestrator:** Airflow is
  the tool being practiced; letting each platform's native scheduler own a
  slice would defeat the point.
- **No Kubernetes:** local Docker Compose Airflow and managed
  Databricks/BigQuery sandboxes are sufficient; there's no multi-service
  app to containerize beyond Airflow itself.
- **No Power BI:** Power BI Desktop (the tool that authors reports) is
  Windows-only; this project is built on macOS. Looker Studio is free,
  browser-based, and connects natively to BigQuery — see ADR-010.

# 5. Repository Layout

```
CMS-Medicare-Claims/
├── CLAUDE.md
├── AGENTS.md
├── PRODUCT_SPEC.md
├── README.md
├── Makefile
├── pyproject.toml                # ruff + black config, see Milestone 8
├── docker-compose.yml            # local Airflow: webserver, scheduler, postgres
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                # lint, unit tests, dbt parse -- no cloud credentials, see §28 Milestone 8
├── .claude/
│   └── agents/
│       └── data-pipeline-reviewer.md
├── docs/
│   ├── IMPLEMENTATION_SPEC.md
│   ├── ARCHITECTURE_DECISIONS.md
│   └── GOVERNANCE.md
├── data/
│   ├── raw/                      # landed CSVs, gitignored
│   └── samples/                  # small committed fixture (few hundred rows)
├── orchestration/
│   └── airflow/
│       └── dags/
│           ├── dag_ingest_beneficiary_raw.py
│           ├── dag_spark_bronze_silver.py
│           ├── dag_full_pipeline.py  # Milestone 8 -- triggers the four DAGs below, fan-out/fan-in
│           ├── dag_dbt_transform.py
│           └── dag_gold_reconcile.py
├── spark_jobs/
│   ├── jobs/
│   │   └── beneficiary_bronze_silver.py   # local runnable job (Milestone 2)
│   ├── transforms/
│   │   └── beneficiary_transforms.py      # shared by the local job AND the Databricks notebook
│   ├── databricks/                        # Milestone 3 — see ADR-007
│   │   ├── deploy.py
│   │   ├── bronze_silver_notebook.py
│   │   └── sql/
│   │       ├── gold_beneficiary_cost_summary.sql
│   │       └── gold_chronic_condition_prevalence.sql
│   └── tests/
│       └── test_beneficiary_transforms.py
├── dbt/
│   ├── requirements.txt
│   └── medicare_claims/
│       ├── dbt_project.yml
│       ├── profiles.yml               # no secrets -- env_var() only, see ADR-008
│       ├── macros/
│       │   └── generate_schema_name.sql
│       ├── seeds/
│       │   └── ssa_state_codes.csv    # same CMS-verified lookup as beneficiary_transforms.py
│       ├── models/
│       │   ├── staging/
│       │   │   ├── _medicare_raw__sources.yml
│       │   │   ├── stg_beneficiary_summary.sql
│       │   │   └── stg_beneficiary_summary.yml
│       │   ├── intermediate/
│       │   │   ├── int_beneficiary_chronic_conditions.sql
│       │   │   └── int_beneficiary_annual_cost.sql
│       │   └── marts/
│       │       ├── dim_beneficiary.sql
│       │       ├── fct_beneficiary_annual_cost.sql
│       │       ├── mart_chronic_condition_prevalence.sql
│       │       └── mart_state_cost_summary.sql
│       └── tests/                     # reserved for singular tests; schema tests live in the .yml files above
├── notebooks/
│   └── 00_data_profiling.ipynb
├── dashboards/
│   └── looker_studio/
│       └── README.md             # report URL + build spec -- no local file, see ADR-010 (report lives entirely in Google's hosted service)
└── streamlit_app/
    ├── app.py
    ├── data_access.py            # BigQuery/DuckDB query layer, see ADR-009
    ├── requirements.txt
    └── tests/
        └── test_data_access.py   # credentials via .env, not .streamlit/secrets.toml -- consistent with every other component
```

# 6. Pipeline-Stage Module Boundaries

## `orchestration/airflow`

Owns all cross-tool scheduling and dependency chaining. Must not contain
business/transformation logic itself — only operators that call out to the
Spark job, dbt project, and BigQuery load steps.

## `spark_jobs`

Owns bronze (raw-typed) and silver (cleaned, decoded, deduplicated) Delta
table logic, written to Databricks Unity Catalog. Must not read from or
write to BigQuery.

## `dbt/medicare_claims`

Owns all BigQuery transformation SQL from `medicare_raw` through staging,
intermediate, and marts. Must not call out to Spark or Databricks.

## `dashboards/looker_studio` and `streamlit_app`

Read-only consumers of gold marts (BigQuery, and for Streamlit optionally
Databricks SQL or local DuckDB). Must not contain transformation logic that
changes reported numbers — if a metric needs new logic, it belongs in dbt or
the Spark silver job, not in a Looker Studio calculated field or Streamlit
query, except for pure presentation (formatting, filtering already-modeled
columns).

# 7. Database Model

## 7.1 Raw source (as delivered by CMS)

### `DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv`

116,352 rows, one per synthetic beneficiary. Key fields:

| Field | Meaning |
|---|---|
| `DESYNPUF_ID` | Synthetic beneficiary ID (natural key) |
| `BENE_BIRTH_DT`, `BENE_DEATH_DT` | Birth date (`YYYYMMDD`), death date if deceased (often blank) |
| `BENE_SEX_IDENT_CD`, `BENE_RACE_CD` | Sex, race codes |
| `BENE_ESRD_IND` | End-stage renal disease indicator |
| `SP_STATE_CODE`, `BENE_COUNTY_CD` | SSA state/county codes |
| `BENE_HI_CVRAGE_TOT_MONS`, `BENE_SMI_CVRAGE_TOT_MONS`, `BENE_HMO_CVRAGE_TOT_MONS`, `PLAN_CVRG_MOS_NUM` | Months of coverage by plan type |
| `SP_ALZHDMTA`, `SP_CHF`, `SP_CHRNKIDN`, `SP_CNCR`, `SP_COPD`, `SP_DEPRESSN`, `SP_DIABETES`, `SP_ISCHMCHT`, `SP_OSTEOPRS`, `SP_RA_OA`, `SP_STRKETIA` | 11 chronic-condition flags, `1=Yes`/`2=No` |
| `MEDREIMB_IP`, `BENRES_IP`, `PPPYMT_IP` | Inpatient: Medicare reimbursement, beneficiary responsibility, primary payer payment |
| `MEDREIMB_OP`, `BENRES_OP`, `PPPYMT_OP` | Same, outpatient |
| `MEDREIMB_CAR`, `BENRES_CAR`, `PPPYMT_CAR` | Same, carrier (physician/supplier) |

## 7.2 Databricks Unity Catalog (lakehouse path) — catalog `medicare`

### `bronze.beneficiary_summary`
Raw CSV columns cast to correct types (dates, decimals), one column added
(`_ingested_at`). No business logic. Grain: one row per `DESYNPUF_ID`.

### `silver.beneficiary`
Cleaned/deduplicated on `DESYNPUF_ID`. Adds: `birth_date`, `death_date`
(typed dates), `age_2008` (computed), `is_deceased` (bool), state name
lookup, decoded chronic-condition booleans (`has_alzheimers`, `has_chf`, …),
`chronic_condition_count`. Grain: one row per beneficiary.

### `gold.beneficiary_cost_summary`
One row per beneficiary: total IP/OP/carrier reimbursement, total
beneficiary responsibility, total cost, chronic condition count, state,
age band. Built with Databricks SQL over `silver.beneficiary`.

### `gold.chronic_condition_prevalence`
One row per condition × state: beneficiary count, prevalence rate, average
total cost for beneficiaries with that condition.

## 7.3 BigQuery (warehouse ELT path)

### `medicare_raw.beneficiary_summary`
Raw load of the CSV, all columns as strings/native CSV types — no
transformation. Loaded by Airflow, not dbt.

### dbt staging — `stg_beneficiary_summary`
Renamed to snake_case, typed, chronic-condition flags decoded to booleans.
1:1 grain with source.

### dbt intermediate
- `int_beneficiary_chronic_conditions` — unpivoted, one row per
  beneficiary × condition, for prevalence analysis.
- `int_beneficiary_annual_cost` — one row per beneficiary, IP/OP/carrier
  reimbursement summed into `total_cost_2008`.

### dbt marts
- `dim_beneficiary` — one row per beneficiary: demographics, state, age
  band, deceased flag, chronic condition count.
- `fct_beneficiary_annual_cost` — grain: one row per beneficiary per year
  (2008 only for now); reimbursement broken out by IP/OP/carrier plus
  totals; foreign key to `dim_beneficiary`.
- `mart_chronic_condition_prevalence` — prevalence and average cost per
  condition, overall and by state.
- `mart_state_cost_summary` — enrollment and total/average cost by state.

# 8. Domain Data Model Notes

The only non-obvious domain rule: CMS encodes the 11 `SP_*` chronic-condition
columns as `1 = Yes`, `2 = No` (not `1/0`). This decoding happens exactly
once per path — in `spark_jobs/transforms/beneficiary_transforms.py` for the
lakehouse path, and in `stg_beneficiary_summary.sql` for the warehouse path
— and nowhere else. `BENE_DEATH_DT` blank means the beneficiary was alive as
of the file's reference date; treat blank/null as `is_deceased = false`, not
as missing data requiring imputation (confirmed against the real file:
98.44% of rows are blank — `notebooks/00_data_profiling.ipynb` §2).

Confirmed by profiling the real file (`notebooks/00_data_profiling.ipynb`
§6): `MEDREIMB_IP` and `MEDREIMB_OP` are **not** guaranteed non-negative — 12
and 51 rows respectively carry negative values (claim adjustments/reversals,
a known feature of CMS reimbursement data), down to −$3,000. Transformation
and aggregation logic must preserve these as-is, never clip to zero or
filter them out as bad data.

# 9. AI Governance Model

N/A — no AI/LLM component is in scope for this project.

# 10. Sensitive Data Handling

See `docs/GOVERNANCE.md`. Summary: CMS DE-SynPUF is public synthetic data
with no re-identification risk, but raw files are still gitignored and
handled with production-grade hygiene (no public buckets, no credentials in
logs) as deliberate practice.

# 11. API Contract

N/A — this project has no first-party backend service. The Streamlit app
queries BigQuery/DuckDB directly through `streamlit_app/data_access.py`
(see §17 for that abstraction). Airflow, Databricks, dbt, and BigQuery are
driven through their own CLIs/SDKs/REST APIs as documented in each tool's
Airflow operator or connection config — not reimplemented here.

# 12. Core Pipeline

Stage by stage:

1. **Ingest** (`dag_ingest_beneficiary_raw`): validate the raw CSV (row
   count, required columns present), copy it to `data/raw/` (or a cloud
   storage bucket), load it as-is into BigQuery `medicare_raw.beneficiary_summary`.
2. **Lakehouse transform** (`dag_spark_bronze_silver`): submit the PySpark
   job to Databricks; it reads the raw CSV, writes `bronze.beneficiary_summary`,
   then `silver.beneficiary`, then refreshes the two `gold.*` tables via
   Databricks SQL.
3. **Warehouse transform** (`dag_dbt_transform`): run `dbt build` against
   BigQuery — staging → intermediate → marts, with tests.
4. **Reconcile** (`dag_gold_reconcile`, optional but recommended): compare
   beneficiary counts and total cost between Databricks `gold.beneficiary_cost_summary`
   and BigQuery `fct_beneficiary_annual_cost`; fail loudly if they diverge.
5. **Serve**: Looker Studio queries BigQuery marts live (direct query, no
   separate refresh schedule to manage); Streamlit queries BigQuery (or
   local DuckDB) live on each user interaction.

# 13. Risk/Safety Routing

N/A — no user-facing AI output or high-risk content in this project.

# 14. Cost & Prevalence Analytics Logic

## Hard constraints

- Chronic-condition flags decoded exactly once per path (§8).
- `total_cost = MEDREIMB_IP + MEDREIMB_OP + MEDREIMB_CAR` (Medicare-paid
  portion only) is the primary cost metric; beneficiary responsibility
  (`BENRES_*`) and primary-payer payments (`PPPYMT_*`) are tracked as
  separate columns, never silently summed into "total cost" without
  labeling which components are included.
- Age is computed from `BENE_BIRTH_DT` relative to 2008-12-31 (the file's
  reference year), banded into standard 10-year bands (65–74, 75–84, 85+,
  matching Medicare-eligible population norms) plus an under-65 band for
  ESRD/disability-based enrollees.

## Candidate scoring / ranking

N/A — no ranking/recommendation logic; this is a descriptive analytics
pipeline (aggregation and prevalence, not prediction) in its core scope.

## LLM role

N/A — no LLM involved.

# 15. Second Domain-Specific Subsystem

N/A for the core build. See §35 for the optional cost-prediction stretch
goal, which would live here if ever promoted out of "future work."

# 16. Frontend Requirements

## Looker Studio (`dashboards/looker_studio/`, report hosted at lookerstudio.google.com — see ADR-010)

Fixed executive report, pages:
- **Overview** — scorecards for total beneficiaries, total 2008
  Medicare-paid cost, and average cost per beneficiary; a geo map of
  enrollment by state.
- **Chronic Conditions** — bar chart of prevalence by condition, bar chart
  of average cost by condition, a chronic-condition-count distribution
  chart.
- **Cost Mix** — IP vs. OP vs. carrier reimbursement split (stacked bar or
  pie), cost by age band (bar chart).

Each page's charts connect directly to BigQuery marts
(`mart_state_cost_summary`, `mart_chronic_condition_prevalence`,
`fct_beneficiary_annual_cost` joined to `dim_beneficiary` for age band) via
Looker Studio's native BigQuery connector — one data source per mart, added
through "Add data → BigQuery," no exported/scheduled extract. There is no
local report file to version-control; `dashboards/looker_studio/README.md`
holds the report's shared URL and the build spec above in copyable form.

## Streamlit (`streamlit_app/app.py`)

Ad hoc exploration app, single page with sidebar filters (state, age band,
chronic condition, deceased/alive) and: a filtered summary table, a cost
distribution chart, and a condition-prevalence chart that update on filter
change. Queries via `data_access.py`, which supports a BigQuery backend and
a local DuckDB backend (loaded from `data/samples/`) selected by an env var,
so the app is runnable with zero cloud cost during development.

# 17. Internal Interfaces

- `streamlit_app/data_access.py` — single module all Streamlit queries go
  through; swappable BigQuery/DuckDB backend behind one interface so the
  app isn't hardcoded to a live cloud connection.
- Airflow connections (`bigquery_default`, `databricks_default`) — all
  project IDs, workspace hosts, and dataset/catalog names come from Airflow
  Variables/Connections or `.env`, never hardcoded in DAG files.
- dbt `profiles.yml` — BigQuery project/dataset/credentials path from env
  vars, never committed with real values.

# 18. Configuration

Environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `GCP_PROJECT_ID` | BigQuery sandbox project |
| `BQ_RAW_DATASET`, `BQ_STAGING_DATASET`, `BQ_MARTS_DATASET` | dbt target datasets |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to local service-account key (gitignored) |
| `DATABRICKS_HOST`, `DATABRICKS_TOKEN` | Databricks workspace connection |
| `UNITY_CATALOG_NAME` | `medicare` |
| `STREAMLIT_BACKEND` | `bigquery` or `duckdb` |
| `AIRFLOW_UID` | Docker Compose local Airflow user |

Secrets live in `.env` (gitignored) and Airflow Connections/Variables (not
committed); `.env.example` documents keys with placeholder values only.

# 19. Local Development

1. `cp .env.example .env` and fill in local/sandbox credentials.
2. `make airflow-up` — local Airflow at `localhost:8081` (`admin`/`admin`;
   pinned off the default 8080 so it doesn't collide with another local
   Airflow stack). `make airflow-logs` tails it; `make airflow-down` stops it.
3. `make ingest-test` — ingestion validation unit tests (no Docker needed).
   `make setup-spark && make spark-test` / `make spark-run` — PySpark unit
   tests and the bronze/silver job, in their own venv (`.venv-spark`,
   Python 3.13 — PySpark doesn't yet support the newer default `python3`
   on this machine) with Java 8/11/17 on `JAVA_HOME`.
4. `make databricks-deploy` — uploads the transform module, driver notebook,
   and gold SQL to the Databricks workspace and creates/updates the
   `medicare_bronze_silver_gold` job; `make databricks-run` also triggers
   and waits on it. See README's "Databricks setup" and ADR-007 (Free
   Edition is serverless-only, which shapes how this job is built).
5. `make dbt-seed` / `make dbt-build` / `make dbt-docs` — load the
   `ssa_state_codes` seed, run all staging/intermediate/mart models plus
   tests, and generate/serve the lineage graph, all against the BigQuery
   sandbox project already used by ingestion. `dag_dbt_transform` runs
   `dbt build` inside Airflow from an isolated venv — see ADR-008.
6. `make streamlit-run` — `streamlit run streamlit_app/app.py` with
   `STREAMLIT_BACKEND=duckdb` for zero-cost local iteration against the
   fixture sample.
7. Looker Studio is opened at lookerstudio.google.com and pointed at the
   BigQuery sandbox project's marts — a browser step, not part of the
   automated `make` targets (there's no local report file/CLI to drive).
   See `dashboards/looker_studio/README.md`.
8. `make airflow-unpause-all && make demo` — the whole pipeline, one
   command: triggers `dag_full_pipeline`, which fans out ingest into
   Databricks + dbt in parallel, then reconciles them. See README's "Full
   pipeline walkthrough."
9. `make lint` / `make format-check` / `make ci` — the same checks
   `.github/workflows/ci.yml` runs, locally, before pushing.

# 20. Testing Strategy

## Unit tests
PySpark transformation functions (`spark_jobs/transforms/`) tested with
small in-memory DataFrames via `pytest` + `chispa`/`pyspark.testing`,
covering: chronic-condition flag decoding, age/age-band computation, cost
aggregation, null-death-date handling.

## Integration tests
dbt tests (`not_null`, `unique` on `DESYNPUF_ID`, `accepted_values` on
sex/race codes, `relationships` from fact to dimension) run on every
`dbt build`.

## End-to-end test
`dag_gold_reconcile` doubles as an e2e check: beneficiary counts and total
cost from the Databricks gold layer and the BigQuery gold layer must match
within a defined tolerance.

## Test data
`data/samples/` holds a committed few-hundred-row fixture drawn from the
real DE-SynPUF file (still synthetic, so safe to commit) for fast unit/local
testing without needing the full 116k-row file or cloud access.

# 21. Evaluation Harness

N/A — no ML model quality bar in the core scope. If §35's optional
cost-prediction stretch goal is built, it gets a small train/test split and
an MAE/R² check, documented at that time.

# 22. Observability and Auditability

- Airflow UI is the primary pipeline observability surface: DAG run history,
  task logs, retries.
- Every bronze/silver/gold and staging table includes an `_ingested_at` /
  `loaded_at` column so any row's pipeline run is traceable.
- `dbt build` output and `dbt docs generate` provide model-level lineage and
  test-pass history for the warehouse path.

# 23. Privacy and Retention Requirements

See `docs/GOVERNANCE.md`. No retention window is required (synthetic public
data), but raw files are never committed and cloud storage buckets/datasets
use least-privilege IAM.

# 24. Security Requirements

- No secrets committed (service-account keys, Databricks tokens, `.env`).
- BigQuery and Databricks access scoped to a dedicated sandbox
  project/workspace, not a shared or production account. The Looker Studio
  report authenticates to BigQuery as the signed-in Google user viewing/
  editing it (Google's own OAuth), not via a stored credential.
- Airflow Connections store credentials in Airflow's encrypted connection
  store, not in DAG code.

# 25. Product Safety / Compliance Language

N/A — no user-facing AI output requiring risk-framing language.

# 26. Third-Party / Public-Figure / Brand Content Rules

N/A. Attribute CMS DE-SynPUF per `docs/GOVERNANCE.md`; no other third-party
content is used.

# 27. Analytics

N/A beyond the project's own subject matter (the dashboards themselves are
the "analytics" this project produces). No usage analytics/telemetry on the
Streamlit app or dashboards is in scope.

# 28. Implementation Milestones

## Milestone 0 — Repository Foundation
### Deliverables
- Repo layout per §5; `.gitignore` excluding `data/raw/`, `.env`, and
  credential files.
- `README.md` with project overview and the commands from §19.
- `data/samples/` fixture (few hundred rows) generated from the source CSV.
- `notebooks/00_data_profiling.ipynb` profiling the raw file (nulls, value
  ranges, flag distributions) to sanity-check assumptions in §7–§8.
### Acceptance criteria
- Repo runs `make` targets (even as stubs) without error; profiling
  notebook runs top to bottom against the real CSV.

## Milestone 1 — Airflow Ingestion
### Deliverables
- `docker-compose.yml` for local Airflow.
- `dag_ingest_beneficiary_raw`: validates and lands the raw CSV, loads it
  into BigQuery `medicare_raw.beneficiary_summary`.
### Acceptance criteria
- DAG runs green locally; `medicare_raw.beneficiary_summary` row count
  matches the source file (116,352).

## Milestone 2 — PySpark Bronze/Silver
### Deliverables
- `spark_jobs/transforms/beneficiary_transforms.py` with unit tests.
- `spark_jobs/jobs/beneficiary_bronze_silver.py` runnable locally against
  the fixture sample.
### Acceptance criteria
- Unit tests pass; local run produces correctly typed bronze output and a
  silver output with decoded flags, computed age/age-band, and
  `chronic_condition_count` matching hand-checked sample rows.

## Milestone 3 — Databricks Unity Catalog
### Deliverables
- Unity Catalog `medicare` with `bronze`/`silver`/`gold` schemas.
- `dag_spark_bronze_silver` submitting the Milestone 2 transform logic to
  Databricks against the full file (as a notebook task on serverless
  compute, not a packaged `spark-submit` job — see ADR-007 for why);
  `gold.beneficiary_cost_summary` and `gold.chronic_condition_prevalence`
  built via Databricks SQL.
### Acceptance criteria — met
- DAG runs green end to end against the real 116,352-row file; gold tables
  queryable from a Databricks SQL warehouse; row/aggregate counts match the
  Milestone 2 local run on the fixture subset.

## Milestone 4 — BigQuery + dbt
### Deliverables
- `dbt/medicare_claims` project: staging, intermediate, and mart models per
  §7.3, with schema tests and `dbt docs`.
- `dag_dbt_transform` running `dbt build` after ingestion, from an isolated
  venv (`/opt/dbt-venv`) rather than Airflow's own — see ADR-008.
### Acceptance criteria — met
- `dbt build` passes all tests (42/42); `dbt docs generate` produces a
  browsable lineage graph; mart row counts/aggregates are sane (spot-checked
  against the profiling notebook — prevalence rates match exactly).

## Milestone 5 — Reconciliation
### Deliverables
- `dag_gold_reconcile` comparing Databricks and BigQuery gold-layer totals.
### Acceptance criteria — met
- DAG fails loudly on an intentionally introduced mismatch (test this once),
  passes on the real matched pipeline. Both verified live: a Databricks SQL
  `UPDATE` (BigQuery Sandbox mode blocks DML, so the deliberate mismatch had
  to go on the Databricks side) produced an exact diagnostic
  (`total_medicare_reimbursement mismatch: Databricks=465234340.00
  BigQuery=465233840.00 (diff=500.00, tolerance=1.0)`); reverting via
  `make databricks-run` restored a passing run.

## Milestone 6 — Looker Studio Dashboard
Originally scoped as a Power BI dashboard; replaced per ADR-010 (Power BI
Desktop is Windows-only, this project is built on macOS — Looker Studio is
free, browser-based, and BigQuery-native, so it's buildable without a VM).
### Deliverables
- A Looker Studio report (Overview / Chronic Conditions / Cost Mix pages
  per §16) connected live to the BigQuery marts, with its shared URL and
  build spec recorded in `dashboards/looker_studio/README.md`.
### Acceptance criteria
- All three pages render against live BigQuery data with no errors; numbers
  match the equivalent dbt mart query run directly.

## Milestone 7 — Streamlit Exploration App
### Deliverables
- `streamlit_app/` per §16–17, both BigQuery and DuckDB backends working.
### Acceptance criteria — met
- App runs locally with `STREAMLIT_BACKEND=duckdb` against the fixture with
  no cloud credentials required; filters update all three views correctly;
  BigQuery backend verified at least once against the sandbox project.
  Verified with a real headless-Chromium/Playwright session (not just unit
  tests): sidebar filters cascade correctly (342 → 7 → 1 beneficiaries),
  zero browser console errors, and the BigQuery backend's numbers match
  Milestone 5's reconciled totals exactly ($465,233,840).

## Milestone 8 — Integrated Demo & Hardening
### Deliverables
- One Airflow DAG (`dag_full_pipeline`, via `TriggerDagRunOperator`
  fan-out/fan-in) demonstrating ingest → Spark/Databricks → dbt/BigQuery →
  reconcile, runnable end to end from a clean state (`make demo`).
- README walkthrough + a simple architecture diagram.
- Basic CI (`.github/workflows/ci.yml`): lint (`ruff`/`black`), PySpark
  unit tests, ingestion/Databricks-job/reconcile and Streamlit unit tests,
  and `dbt parse` (structural validation, not a full `dbt build` — that
  needs live BigQuery credentials, which isn't worth wiring into CI for
  this project; real `dbt build` verification already happened manually
  and is documented with exact numbers). All on GitHub's free tier.
### Acceptance criteria — met
- A cold clone of the repo, following the README, can reproduce the full
  pipeline through to both BI surfaces using only sandbox/free-tier
  credentials. Verified live: `dag_full_pipeline` triggered end to end,
  all four sub-DAGs succeeded, the two parallel branches (Databricks,
  dbt/BigQuery) genuinely ran concurrently (confirmed via task timestamps),
  and `dag_gold_reconcile` reconciled to the exact expected totals
  (116,352 beneficiaries, $465,233,840) in ~2.5 minutes start to finish.

# 29. First Tasks for the Coding Agent

## Task 1
Scaffold Milestone 0: repo layout, `.gitignore`, `README.md` skeleton,
`.env.example`, and generate `data/samples/` from the real CSV (first ~300
rows plus a stratified sample across states/conditions, not just a head).

## Task 2
Write and run `notebooks/00_data_profiling.ipynb` against the real CSV to
confirm the assumptions in §7–§8 (flag encoding, death-date null rate,
value ranges) before any transformation code is written.

## Task 3
Implement `spark_jobs/transforms/beneficiary_transforms.py` with unit tests
(Milestone 2), using the profiling results from Task 2 to drive test cases.

## Task 4
Set up local Airflow (`docker-compose.yml`) and `dag_ingest_beneficiary_raw`
(Milestone 1), validated against the fixture sample before pointing it at
the full file or real cloud credentials.

# 30. Coding Standards

## Python
`black` + `ruff` formatting/linting; type hints on all PySpark transform
functions and the Streamlit data-access layer; no bare `except:`.

## SQL (dbt / BigQuery / Databricks SQL)
`sqlfluff` (or dbt's built-in style conventions) for formatting; every dbt
model has a corresponding `.yml` with column descriptions and tests; CTEs
named descriptively, no unaliased joins.

## Airflow
One DAG per file, DAG IDs matching filenames, all cross-tool config via
Connections/Variables, no inline credentials.

# 31. Git and Change Discipline

Conventional commit-style messages (`feat:`, `fix:`, `docs:`); one milestone
roughly maps to one PR/commit series; schema changes require an ADR entry
first; human review (self-review is fine for a solo portfolio project, but
run the diff against `docs/IMPLEMENTATION_SPEC.md` before merging).

# 32. Architecture Decision Records

See `docs/ARCHITECTURE_DECISIONS.md` (ADR-001 through ADR-006 as of this
writing) — not duplicated here.

# 33. Definition of Done

The full pipeline (Milestone 8) runs from a clean clone using only
sandbox/free-tier cloud credentials; both BI surfaces show matching numbers
sourced from tested, documented models; no secrets or raw data are
committed; README accurately documents every command needed to reproduce
the build.

# 34. Portfolio-Build Completion Criteria

The project is "interview-ready" when the developer can, without notes,
walk through: the Airflow DAG graph, the Unity Catalog bronze/silver/gold
lineage, the dbt docs lineage graph, and both dashboards — explaining one
non-obvious design decision (from `docs/ARCHITECTURE_DECISIONS.md`) at each
stage.

# 35. Future Work — Do Not Implement Yet

- Ingest the companion DE-SynPUF Inpatient/Outpatient/Carrier Claims and PDE
  files for the same beneficiary IDs, joined to the beneficiary dimension.
- Multi-year DE-SynPUF releases (2008–2010) for a trend/time-series layer.
- Optional cost-prediction stretch goal: a simple scikit-learn regression
  (chronic condition count + age band + state → total cost) surfaced as an
  extra Streamlit tab — explicitly optional, never a core milestone.
- CI/CD deployment automation for Databricks Jobs and dbt Cloud.
- Row-level access control / multi-user Streamlit auth.

# 36. Final Agent Directive

Build one milestone at a time, in order, and stop at each boundary unless
told to continue. Every number that ends up on a dashboard must trace back
to a single, tested piece of transformation code — never to logic invented
inside Looker Studio or a Streamlit query. When a tool-specific decision isn't
covered here, prefer the choice that gives that tool a real, defensible role
in an interview conversation over the choice that's merely fastest to wire
up.
