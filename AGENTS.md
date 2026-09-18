# AGENTS.md — Medicare Claims Analytics Platform

Read `docs/IMPLEMENTATION_SPEC.md` before making architectural or feature
changes.

## Mission

Build a portfolio-grade Medicare data platform on the public CMS DE-SynPUF
2008 Beneficiary Summary File that demonstrates real, orchestrated use of
Airflow, PySpark, Databricks/Unity Catalog, dbt, BigQuery, Power BI, and
Streamlit — in that pipeline order, not as isolated demos.

## Current priority

Implement milestones in the exact order defined in
`docs/IMPLEMENTATION_SPEC.md` §28.

If starting from an empty repository, begin with **Milestone 0 — Repository
Foundation**. Do not scaffold Airflow DAGs, Spark jobs, dbt models, and both
BI layers all at once before the foundation (repo structure, `.gitignore`,
`.env.example`, data profiling) is in place.

## Non-negotiable rules

- PySpark writes only to Databricks Unity Catalog tables (`catalog.schema.table`),
  never to `hive_metastore` or an unmanaged path.
- BigQuery transformation SQL lives only in the dbt project — no console-created
  views/tables for anything a dbt model already owns.
- Airflow is the only place cross-tool steps are chained; don't hand-trigger
  a Spark job or dbt run that a DAG already owns.
- Never ingest anything but the CMS DE-SynPUF public synthetic files. Never
  real Medicare/PHI/PII data, in dev or prod.
- Every pipeline job (ingestion, Spark, dbt) must be idempotent and safe to
  re-run.
- Do not commit secrets, raw data files, `.pbix` files with embedded
  credentials, or real sensitive user data.

## Engineering behavior

- Make the smallest coherent change that advances the current milestone.
- Add/update tests with each change (PySpark unit tests, dbt tests).
- Keep cloud project IDs, workspace hosts, and warehouse names in config/env,
  never hardcoded in DAGs, Spark jobs, or dbt profiles.
- Do not silently modify the bronze/silver/gold or staging/mart schemas —
  record the change in `docs/ARCHITECTURE_DECISIONS.md` first.
- Keep README developer commands (docker-compose up, dbt build, spark-submit,
  streamlit run) accurate as the project grows.
- Stop at milestone boundaries unless instructed to continue.

## Required source of truth

See:

- `docs/IMPLEMENTATION_SPEC.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/GOVERNANCE.md`

If these conflict, prefer the most recent explicit human decision and update
the documents so the repository has one coherent source of truth.
