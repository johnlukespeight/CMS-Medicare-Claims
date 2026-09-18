# Medicare Claims Analytics Platform — Portfolio Project Specification

## 1. Executive Summary

A self-directed data engineering portfolio project built to prepare for data
engineering interviews by giving hands-on, demonstrable depth with a
specific, commonly-required toolchain: Apache Airflow, dbt, PySpark,
Databricks SQL/Unity Catalog, BigQuery, Power BI, and Streamlit. Rather than
a tutorial-style demo of each tool in isolation, it's one real pipeline
built on public CMS Medicare data where each tool plays the role it plays in
a real DE org.

## 2. Market Reality

Data engineering job postings routinely list this exact combination —
an orchestrator (Airflow), a transformation layer (dbt), a big-data
processing engine (Spark), a lakehouse platform (Databricks/Unity Catalog),
a cloud warehouse (BigQuery or a peer), and a BI layer (Power BI, plus
increasingly a lightweight Python app like Streamlit for internal tools).
Interviewers want to hear about trade-offs made across these tools, not just
that each was "used."

## 3. Target Users and Jobs to Be Done

The primary "user" of this project is the developer's own interview
preparation: producing concrete, explainable artifacts (DAG graphs, Unity
Catalog lineage, dbt docs, two working dashboards) to reference in system-
design and behavioral interview answers. A secondary audience is anyone
reviewing the developer's GitHub as part of a hiring process.

## 4. Build-Stage Objective

Ship one coherent, orchestrated pipeline from raw CMS DE-SynPUF data through
both a lakehouse and a warehouse analytical layer, ending in two working
dashboards — with every stage individually defensible in an interview.

## 5. Build-Stage Non-Goals

See `docs/IMPLEMENTATION_SPEC.md` §3 and §35 — no streaming, no real
Medicare data, no additional claims files until explicitly added, no
productionized ML.

## 6. Build-Stage Success Criteria

- All 8 milestones in `docs/IMPLEMENTATION_SPEC.md` §28 complete and green.
- A cold clone can reproduce the full pipeline using only free-tier/sandbox
  credentials.
- The developer can explain, unprompted, why the pipeline is split into a
  lakehouse path and a warehouse path (ADR-001) and why Airflow — not each
  tool's native scheduler — owns orchestration (ADR-004).

## 7. Product Architecture

See `docs/IMPLEMENTATION_SPEC.md` §4–§6 and §12 for the full stage-by-stage
architecture and module boundaries.

## 8. Core Subsystem — Lakehouse (Databricks / Unity Catalog / PySpark)

Bronze/silver/gold Delta tables under Unity Catalog, built by PySpark jobs
orchestrated from Airflow. See spec §7.2, §14.

## 9. Core Subsystem — Warehouse ELT (BigQuery / dbt)

Raw-to-marts transformation entirely owned by dbt, targeting BigQuery. See
spec §7.3.

## 10. Data Model

See `docs/IMPLEMENTATION_SPEC.md` §7–§8.

## 11. Recommended Technology Stack

Airflow (Docker Compose locally), Databricks (free/Community or trial
workspace) with Unity Catalog, PySpark, Google BigQuery (sandbox project),
dbt-core with the `dbt-bigquery` adapter, Power BI Desktop/Service, and
Streamlit with a DuckDB local-dev fallback.

## 12. Privacy, Security, and Data Retention

See `docs/GOVERNANCE.md`.

## 13. Regulatory/Compliance Boundary

None applicable — CMS DE-SynPUF is public synthetic data with no
HIPAA/PHI exposure. This project must never be extended to real Medicare
claims (ADR-006).

## 14. Model and Dataset Governance

See `docs/GOVERNANCE.md`. Dataset: CMS DE-SynPUF 2008 Beneficiary Summary
File, Sample 1, 116,352 records.

## 15. Evaluation Plan

N/A for the core build (descriptive analytics, not ML). See spec §21 and
§35 for the optional, non-core cost-prediction stretch goal.

## 16. Build Plan (by milestone)

See `docs/IMPLEMENTATION_SPEC.md` §28 for the full 9-milestone (0–8) build
plan with deliverables and acceptance criteria per milestone.

## 17. Main Risks

- **Cloud cost creep:** mitigated by sandbox projects, free-tier limits, and
  idempotent/re-runnable jobs (hard constraint in `CLAUDE.md`).
- **Tool sprawl without depth:** mitigated by giving each tool one clear,
  non-overlapping responsibility (§6 of the spec) rather than letting
  responsibilities blur.
- **Schema drift silently breaking dashboards:** mitigated by dbt tests, the
  gold-layer reconciliation DAG, and the ADR-before-schema-change rule.

## 18. Recommended First Demo

Milestone 4 (BigQuery + dbt) plus Milestone 7 (Streamlit) is the earliest
point with a genuinely demoable artifact: a working, tested ELT pipeline
with a live filterable app on top — useful as an interim portfolio link
before Milestones 3/6 (Databricks, Power BI) are finished.

## 19. Go/No-Go Decision After Build

Go criterion: all of §6's success criteria are met and the developer can
give a 5-minute unscripted walkthrough of the pipeline end to end. If not,
extend the timeline rather than cut milestones — partial-tool depth defeats
the project's purpose.

## 20. Research and Regulatory Basis

CMS DE-SynPUF public documentation (synthetic data methodology, codebook
for field encodings referenced in `docs/IMPLEMENTATION_SPEC.md` §7–§8).
