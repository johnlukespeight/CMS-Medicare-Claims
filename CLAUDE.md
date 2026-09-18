# CLAUDE.md — Medicare Claims Analytics Platform

Before implementing changes, read `docs/IMPLEMENTATION_SPEC.md`.

## Project objective

Medicare Claims Analytics Platform is a portfolio-grade data engineering
project built on the public CMS DE-SynPUF 2008 Beneficiary Summary File
(Sample 1) that exercises the full modern DE toolchain end to end. The core
vertical slice is:

**Raw CSV landed via Airflow → PySpark bronze/silver on Databricks (Unity
Catalog) → BigQuery raw load → dbt staging/marts → Power BI executive
dashboard + Streamlit exploration app**

The point of the project is depth of tool usage, not dataset breadth: one
well-modeled beneficiary file, run through a real orchestrated pipeline, beats
five files glued together with scripts.

## Implementation order

Follow the milestones in `docs/IMPLEMENTATION_SPEC.md` (§28). Do not skip
ahead to real-time/streaming ingestion, ingesting the other DE-SynPUF files
(Inpatient/Outpatient/Carrier Claims, PDE), ML model productionization,
multi-user auth, or Kubernetes — all listed as future work in §35.

## Hard constraints

1. Lakehouse-first processing: PySpark writes Delta tables to Databricks
   Unity Catalog (`bronze` → `silver` → `gold`); never write to
   `hive_metastore` or an ungoverned path.
2. Warehouse ELT: all BigQuery transformation SQL lives in the dbt project
   (`dbt/medicare_claims/`). No hand-written views/tables in the BigQuery
   console once a dbt model owns that table.
3. Airflow is the single orchestrator across tool boundaries (ingest → Spark/
   Databricks → dbt/BigQuery). No manual triggering of a step once its
   milestone has an Airflow DAG for it.
4. Two BI surfaces, two audiences, don't collapse them: Power BI is the fixed
   executive dashboard; Streamlit is the ad hoc/self-serve exploration app.
5. Only CMS DE-SynPUF public synthetic files may ever be ingested. Never real
   Medicare claims, PHI, or PII — in dev or prod. See `docs/GOVERNANCE.md`.
6. Cloud resources (BigQuery, Databricks) stay within free-tier/sandbox
   limits. Every job must be idempotent — safe to re-run without duplicating
   rows or incurring duplicate cost.
7. Schema changes to any bronze/silver/gold/staging/mart table require a new
   entry in `docs/ARCHITECTURE_DECISIONS.md` before the change merges.
8. Deterministic code controls all cost and flag-decoding logic (e.g.
   chronic-condition flag `1=Yes`/`2=No`, IP/OP/Carrier reimbursement
   aggregation) — never inferred ad hoc inside a dashboard or notebook.
9. Add tests with each feature: PySpark unit tests for transformation logic;
   dbt tests (`not_null`, `unique`, `accepted_values`, `relationships`) on
   every staging and mart model.
10. Do not commit raw data files, service-account keys, Databricks tokens, or
    `.pbix`/`.env` files containing credentials.
11. Do not introduce Kafka/streaming, Kubernetes, Great Expectations/Soda, or
    a second orchestrator for this build without an explicit ADR.
12. Stop at a milestone boundary unless asked to continue.

## When uncertain

Prefer:

- one well-modeled table over five shallow ones;
- explicit, testable transformation logic over dashboard-side calculations;
- idempotent, re-runnable jobs over one-shot scripts;
- provider abstractions (config-driven connection strings/creds) over
  hardcoded project IDs, workspace URLs, or hostnames;
- synthetic/public DE-SynPUF data only, never invented "realistic" PII for
  testing.

See `docs/IMPLEMENTATION_SPEC.md` for schemas, the dbt model DAG, Airflow DAG
layout, milestones, acceptance criteria, coding standards, and the exact
first tasks.
