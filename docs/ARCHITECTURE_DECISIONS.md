# Medicare Claims Analytics Platform — Architecture Decisions

## ADR-001 — Split the platform into a lakehouse path and a warehouse ELT path

**Status:** Accepted
**Context:** The tool list to practice (Airflow, dbt, PySpark, Databricks/
Unity Catalog, BigQuery, Power BI, Streamlit) spans two competing data
platform paradigms — lakehouse and cloud warehouse — and a single pipeline
can't exercise both meaningfully.
**Decision:** Build two parallel processing paths off the same raw landing
zone: (1) PySpark on Databricks writing Delta tables governed by Unity
Catalog (bronze → silver → gold), and (2) a raw BigQuery load transformed by
dbt (staging → intermediate → marts). Both are orchestrated by the same
Airflow instance.
**Consequences:** More moving parts than a single pipeline, but each tool
gets a real, idiomatic use case instead of a token integration. Gold tables
in both platforms model the same beneficiary grain so they can be sanity-
checked against each other.

## ADR-002 — Databricks Unity Catalog owns the lakehouse namespace

**Status:** Accepted
**Context:** Need a concrete, governed table namespace for the Spark output
rather than ad hoc paths.
**Decision:** All Spark-written tables live under a single Unity Catalog
catalog (`medicare`), with schemas `bronze`, `silver`, `gold`. No table is
ever written to the legacy `hive_metastore`.
**Consequences:** Requires a Unity Catalog-enabled workspace before Milestone
2 can complete; rules out any quick-and-dirty local-path Delta write as the
"real" version of a table.

## ADR-003 — dbt owns all BigQuery transformation SQL

**Status:** Accepted
**Context:** BigQuery allows ad hoc views/tables from the console, which
would bypass version control, tests, and documentation.
**Decision:** Once a dbt model exists for a given BigQuery table, all further
changes to its logic happen in the dbt project (`dbt/medicare_claims/`). Raw
data lands via Airflow directly into a `medicare_raw` dataset; everything
downstream of that is a dbt model.
**Consequences:** Slightly slower to prototype a one-off query, but every
transformation is testable, documented (`dbt docs generate`), and diffable.

## ADR-004 — Airflow is the single cross-tool orchestrator

**Status:** Accepted
**Context:** With five+ tools in the pipeline, it would be easy to let each
tool's own scheduler (Databricks Jobs, dbt Cloud, cron) own a slice, making
the overall pipeline hard to reason about or demo end to end.
**Decision:** Airflow DAGs trigger the Databricks job (via
`DatabricksSubmitRunOperator` or REST call) and the dbt run (via
`BashOperator`/Cosmos), rather than those tools' native schedulers.
**Consequences:** Airflow becomes the one place to look for pipeline state
and lineage across tools — the interview-relevant skill this project is
built to demonstrate.

## ADR-005 — Two BI surfaces for two audiences

**Status:** Accepted
**Context:** Power BI and Streamlit serve different purposes and the task
explicitly calls out Streamlit as a "second use case," not a Power BI
replacement.
**Decision:** Power BI hosts a fixed executive dashboard (enrollment,
chronic-condition prevalence, cost mix) sourced from BigQuery gold marts.
Streamlit hosts an ad hoc, filterable exploration app (cohort filters by
state/age/condition) against the same marts, with a local DuckDB fallback
for offline/no-cost iteration.
**Consequences:** Two BI codebases to maintain, but each demonstrates a
distinct, real-world BI pattern (fixed reporting vs. self-serve exploration)
rather than one tool duplicating the other.

## ADR-006 — CMS DE-SynPUF only, no real Medicare data, ever

**Status:** Accepted
**Context:** Medicare claims data is a sensitive category even when publicly
released; the project name and dataset invite confusion with real PHI.
**Decision:** This repository and every pipeline in it may only ever ingest
CMS DE-SynPUF public synthetic files. See `docs/GOVERNANCE.md`.
**Consequences:** Rules out ever wiring this pipeline to a real claims feed
without a new, explicit ADR and a full governance rewrite.

## ADR-007 — Databricks Free Edition (serverless-only) changes how the bronze/silver job ships

**Status:** Accepted
**Context:** Milestone 3 was originally scoped assuming a classic Databricks
cluster (a `spark-submit`-style job, like Milestone 2's local run). The
actual workspace provisioned (Databricks Free Edition) has **zero classic
clusters available** — confirmed via `GET /api/2.1/clusters/list` returning
an empty list — only serverless compute (one SQL Warehouse, and serverless
notebook/job execution). This is a real platform constraint discovered
during implementation, not a design preference.
**Decision:**
- The bronze/silver step ships as a Databricks **notebook task** run on
  serverless compute, not a packaged `spark-submit` job. The notebook
  (`spark_jobs/databricks/bronze_silver_notebook.py`) imports and calls the
  *exact same* `spark_jobs/transforms/beneficiary_transforms.py` used
  locally in Milestone 2 — uploaded as a plain workspace **file** (not a
  notebook; format=`AUTO` with no `language` param, or Databricks silently
  wraps it as a notebook and the import fails) alongside the driver
  notebook, so the transform logic itself is never duplicated.
- The raw CSV is uploaded to a Unity Catalog **Volume**
  (`medicare.bronze.raw_files`) via the Files API rather than DBFS, keeping
  file storage under Unity Catalog governance too, not just tables.
- The gold layer runs as two Databricks SQL **file tasks** (also plain
  workspace files, same AUTO-format caveat) against the one available SQL
  Warehouse, chained as dependents of the bronze/silver task in a single
  persisted Databricks Job (`medicare_bronze_silver_gold`), deployed
  idempotently by `spark_jobs/databricks/deploy.py`.
- `orchestration/airflow/dags/dag_spark_bronze_silver.py` only triggers and
  polls that pre-deployed job by name (via the plain Databricks REST API,
  matching `dag_ingest_beneficiary_raw.py`'s style) — it does not deploy.
**Consequences:** No cluster-sizing/autoscaling config to reason about,
which is one less thing to demo — a fair trade for a portfolio project, but
worth being upfront about in an interview: this is not how a job would ship
against a workspace with classic clusters available. Verified end to end
against the real 116,352-row file: bronze/silver/gold row counts match
Milestone 2's local run exactly, and `gold.chronic_condition_prevalence`'s
overall rates match `notebooks/00_data_profiling.ipynb`'s findings exactly
(e.g. ischemic heart disease 42.1%, diabetes 37.9%).
