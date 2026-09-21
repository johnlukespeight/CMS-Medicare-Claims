# Looker Studio Dashboard — Build Spec

Milestone 6. Replaces the originally-planned Power BI dashboard — see
[ADR-010](../../docs/ARCHITECTURE_DECISIONS.md#adr-010--power-bi-replaced-with-looker-studio-for-the-fixed-dashboard).
There is no local report file: Looker Studio reports live entirely in
Google's hosted service. This file is the report's source of truth in the
repo — the exact fields/charts to build, plus the report's shared URL once
it exists.

**Report URL:** _not yet created — paste the shared "anyone with the link
can view" URL here once built._

## Data sources

Three data sources, each a **native BigQuery table connection** except
Cost Mix, which needs a **Custom Query** (Looker Studio's BigQuery
connector supports pasting raw SQL as the data source) since it joins two
marts — the same kind of read-only, no-new-logic join
[ADR-009](../../docs/ARCHITECTURE_DECISIONS.md#adr-009--streamlits-bigquery-backend-reads-stg_beneficiary_summary-staging-not-just-marts)
already established is fine for a consumer to do.

| Data source | Type | Source |
|---|---|---|
| `ls_overview` | BigQuery table | `medicare_marts.mart_state_cost_summary` |
| `ls_condition_prevalence` | BigQuery table | `medicare_marts.mart_chronic_condition_prevalence` |
| `ls_beneficiary_dim` | BigQuery table | `medicare_marts.dim_beneficiary` |
| `ls_cost_mix` | BigQuery custom query | see below |

**`ls_cost_mix` custom query:**

```sql
SELECT
  fct.desynpuf_id,
  fct.medreimb_ip,
  fct.medreimb_op,
  fct.medreimb_car,
  fct.total_medicare_reimbursement,
  dim.age_band
FROM `medicare-claims-de-synpuf.medicare_marts.fct_beneficiary_annual_cost` AS fct
JOIN `medicare-claims-de-synpuf.medicare_marts.dim_beneficiary` AS dim
  ON fct.desynpuf_id = dim.desynpuf_id
```

Connect all four as the same Google account already used for the GCP
sandbox project (§ "Looker Studio setup" in the repo root README).

## Page 1 — Overview

Data source: `ls_overview`.

- **Scorecard** — `SUM(beneficiary_count)`, labeled "Total Beneficiaries".
- **Scorecard** — `SUM(total_medicare_reimbursement)`, currency format,
  labeled "Total Medicare-Paid Cost (2008)".
- **Scorecard** — add a calculated field
  `avg_cost_per_beneficiary = SUM(total_medicare_reimbursement) / SUM(beneficiary_count)`,
  currency format, labeled "Avg Cost / Beneficiary". (A ratio over
  already-modeled columns — pure presentation, not new business logic.)
- **Geo map (State)** — Location dimension = `state_name`, metric =
  `beneficiary_count`. Looker Studio's built-in US States geography
  recognizes full names like "California" directly.

Verify against: `bq query --use_legacy_sql=false "SELECT SUM(beneficiary_count), SUM(total_medicare_reimbursement) FROM medicare_marts.mart_state_cost_summary"`
— should read 116,352 and $465,233,840 (Milestone 5's reconciled totals).

## Page 2 — Chronic Conditions

Data source: `ls_condition_prevalence`, **filtered to `state_name = "All States"`**
(the mart's pre-aggregated overall rows — 11 rows, one per condition).

- **Bar chart** — dimension = `condition`, metric = `prevalence_rate`,
  percent format, sorted descending. Labeled "Prevalence by Condition".
- **Bar chart** — dimension = `condition`, metric =
  `avg_total_cost_with_condition`, currency format, sorted descending.
  Labeled "Average Cost by Condition".

Switch to data source `ls_beneficiary_dim` for the third chart:

- **Bar chart** — dimension = `chronic_condition_count`, metric = Record
  Count. Labeled "Chronic Condition Count Distribution".

Verify against: the exact prevalence percentages in
`notebooks/00_data_profiling.ipynb` §6 / `mart_chronic_condition_prevalence`
directly — e.g. ischemic heart disease 42.06%, diabetes 37.87%.

## Page 3 — Cost Mix

Data source: `ls_cost_mix`.

- **Stacked bar or pie chart** — three metrics: `SUM(medreimb_ip)`,
  `SUM(medreimb_op)`, `SUM(medreimb_car)`. Labeled "IP vs OP vs Carrier
  Reimbursement Split".
- **Bar chart** — dimension = `age_band`, metric =
  `SUM(total_medicare_reimbursement)`. Labeled "Cost by Age Band".
  **Sort order gotcha:** Looker Studio sorts dimension values
  alphabetically by default, which puts them in the wrong order
  (`65-74`, `75-84`, `85+`, `Under 65`). Either set a manual sort order in
  the chart's Style panel, or add a calculated `age_band_sort_key` field
  (`CASE WHEN age_band = "Under 65" THEN 0 WHEN age_band = "65-74" THEN 1
  WHEN age_band = "75-84" THEN 2 ELSE 3 END`) and sort by that instead.

## Verifying the finished report

Once the report URL is pasted in above and link-sharing is set to **"Anyone
with the link can view"** (view only, not edit — no Google sign-in required
to view at that setting), it can be opened read-only in a headless browser
to confirm it renders — the same way Milestone 7's Streamlit app was
verified with Playwright, rather than stopping at "the code should work."
