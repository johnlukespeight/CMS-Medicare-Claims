"""Single data-access layer for the Streamlit app — every query the app
runs goes through here, behind one interface, so `app.py` never knows
which backend (BigQuery or local DuckDB) it's talking to.

See docs/IMPLEMENTATION_SPEC.md §16-17 (Milestone 7).

Both backends return the same per-beneficiary shape (one row per
beneficiary: demographics/state/age-band/cost/the 11 condition flags), so
all filtering and aggregation for the app's three views happens once, in
pandas, in app.py — not duplicated per backend.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV_PATH = REPO_ROOT / "data" / "samples" / "beneficiary_summary_sample.csv"
# Reused as-is, not re-derived: the same CMS-codebook-verified SSA state
# lookup dbt's staging/marts already use (dbt/medicare_claims/seeds), not a
# fifth independent copy — this is the same Streamlit app's own local-dev
# convenience path, not a separate pipeline (unlike the Spark/dbt paths,
# where ADR-001 calls for owning decode logic independently).
SSA_STATE_CODES_PATH = REPO_ROOT / "dbt" / "medicare_claims" / "seeds" / "ssa_state_codes.csv"

CONDITION_COLUMNS = [
    "has_alzheimers",
    "has_chf",
    "has_chronic_kidney_disease",
    "has_cancer",
    "has_copd",
    "has_depression",
    "has_diabetes",
    "has_ischemic_heart_disease",
    "has_osteoporosis",
    "has_rheumatoid_or_osteoarthritis",
    "has_stroke_or_tia",
]

BENEFICIARY_COLUMNS = [
    "desynpuf_id",
    "state_abbr",
    "state_name",
    "age_band",
    "is_deceased",
    "chronic_condition_count",
    "total_medicare_reimbursement",
    *CONDITION_COLUMNS,
]


def load_beneficiary_gold(backend: str | None = None) -> pd.DataFrame:
    """Loads the per-beneficiary dataset for the given backend
    ("bigquery" or "duckdb"; defaults to the STREAMLIT_BACKEND env var).
    """
    backend = backend or os.environ.get("STREAMLIT_BACKEND", "duckdb")
    if backend == "duckdb":
        return _load_from_duckdb()
    if backend == "bigquery":
        return _load_from_bigquery()
    raise ValueError(f"Unknown STREAMLIT_BACKEND: {backend!r} (expected 'bigquery' or 'duckdb')")


def _duckdb_query() -> str:
    # Age is computed as (2008 - birth_year): correct for every birth date
    # because the reference date is 2008-12-31 (the last day of the year),
    # so the birthday has always already occurred -- same reasoning
    # verified empirically against BigQuery's DATE_DIFF in Milestone 4.
    condition_flags_sql = ",\n        ".join(
        f"(SP_{raw} = '1') as {col}"
        for raw, col in [
            ("ALZHDMTA", "has_alzheimers"),
            ("CHF", "has_chf"),
            ("CHRNKIDN", "has_chronic_kidney_disease"),
            ("CNCR", "has_cancer"),
            ("COPD", "has_copd"),
            ("DEPRESSN", "has_depression"),
            ("DIABETES", "has_diabetes"),
            ("ISCHMCHT", "has_ischemic_heart_disease"),
            ("OSTEOPRS", "has_osteoporosis"),
            ("RA_OA", "has_rheumatoid_or_osteoarthritis"),
            ("STRKETIA", "has_stroke_or_tia"),
        ]
    )
    condition_count_sql = " + ".join(f"cast({col} as int)" for col in CONDITION_COLUMNS)

    return f"""
        with raw as (
            select * from read_csv_auto('{SAMPLE_CSV_PATH.as_posix()}', header=true, all_varchar=true)
        ),
        casted as (
            select
                DESYNPUF_ID as desynpuf_id,
                lpad(SP_STATE_CODE, 2, '0') as state_code,
                (BENE_DEATH_DT is not null and BENE_DEATH_DT != '') as is_deceased,
                (2008 - extract(year from strptime(BENE_BIRTH_DT, '%Y%m%d'))) as age_2008,
                cast(MEDREIMB_IP as double) + cast(MEDREIMB_OP as double) + cast(MEDREIMB_CAR as double)
                    as total_medicare_reimbursement,
                {condition_flags_sql}
            from raw
        ),
        with_state as (
            select
                casted.*,
                ssa.state_abbr,
                ssa.state_name
            from casted
            left join read_csv_auto('{SSA_STATE_CODES_PATH.as_posix()}', header=true, all_varchar=true) as ssa
                on casted.state_code = ssa.state_code
        )
        select
            desynpuf_id,
            state_abbr,
            state_name,
            case
                when age_2008 < 65 then 'Under 65'
                when age_2008 < 75 then '65-74'
                when age_2008 < 85 then '75-84'
                else '85+'
            end as age_band,
            is_deceased,
            ({condition_count_sql}) as chronic_condition_count,
            total_medicare_reimbursement,
            {", ".join(CONDITION_COLUMNS)}
        from with_state
    """


def _load_from_duckdb() -> pd.DataFrame:
    import duckdb

    return duckdb.sql(_duckdb_query()).df()


def _load_from_bigquery() -> pd.DataFrame:
    from google.cloud import bigquery

    project_id = os.environ["GCP_PROJECT_ID"]
    marts_dataset = os.environ.get("BQ_MARTS_DATASET", "medicare_marts")
    # dim_beneficiary/fct_beneficiary_annual_cost (marts) don't carry
    # per-condition flags at the beneficiary grain (only the aggregate
    # chronic_condition_count) -- no mart currently does, since nothing
    # upstream needed per-beneficiary flags until this app's cross-filters
    # did. Reading stg_beneficiary_summary (staging) here for those flags
    # is a deliberate, documented boundary crossing: read-only, no new
    # business logic (decoding already happened in dbt), see ADR-009.
    staging_dataset = os.environ.get("BQ_STAGING_DATASET", "medicare_staging")

    condition_cols_sql = ", ".join(f"stg.{col}" for col in CONDITION_COLUMNS)
    query = f"""
        select
            dim.desynpuf_id,
            dim.state_abbr,
            dim.state_name,
            dim.age_band,
            dim.is_deceased,
            dim.chronic_condition_count,
            fct.total_medicare_reimbursement,
            {condition_cols_sql}
        from `{project_id}.{marts_dataset}.dim_beneficiary` as dim
        join `{project_id}.{marts_dataset}.fct_beneficiary_annual_cost` as fct
            on dim.desynpuf_id = fct.desynpuf_id
        join `{project_id}.{staging_dataset}.stg_beneficiary_summary` as stg
            on dim.desynpuf_id = stg.desynpuf_id
    """
    client = bigquery.Client(project=project_id)
    return client.query(query).to_dataframe()
