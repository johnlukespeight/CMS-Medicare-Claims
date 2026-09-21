"""Pure, framework-agnostic logic for the beneficiary-summary ingestion DAG.

Kept separate from `dag_ingest_beneficiary_raw.py` so it's unit-testable
without an Airflow environment — see
`orchestration/airflow/tests/test_beneficiary_ingest.py`. Raises plain
`ValueError` on failure; the DAG task wrappers translate that into
`AirflowException` so failures render correctly in the Airflow UI.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

# Matches docs/IMPLEMENTATION_SPEC.md §7.1 — the raw CMS DE-SynPUF column set.
EXPECTED_COLUMNS = [
    "DESYNPUF_ID",
    "BENE_BIRTH_DT",
    "BENE_DEATH_DT",
    "BENE_SEX_IDENT_CD",
    "BENE_RACE_CD",
    "BENE_ESRD_IND",
    "SP_STATE_CODE",
    "BENE_COUNTY_CD",
    "BENE_HI_CVRAGE_TOT_MONS",
    "BENE_SMI_CVRAGE_TOT_MONS",
    "BENE_HMO_CVRAGE_TOT_MONS",
    "PLAN_CVRG_MOS_NUM",
    "SP_ALZHDMTA",
    "SP_CHF",
    "SP_CHRNKIDN",
    "SP_CNCR",
    "SP_COPD",
    "SP_DEPRESSN",
    "SP_DIABETES",
    "SP_ISCHMCHT",
    "SP_OSTEOPRS",
    "SP_RA_OA",
    "SP_STRKETIA",
    "MEDREIMB_IP",
    "BENRES_IP",
    "PPPYMT_IP",
    "MEDREIMB_OP",
    "BENRES_OP",
    "PPPYMT_OP",
    "MEDREIMB_CAR",
    "BENRES_CAR",
    "PPPYMT_CAR",
]

# Sanity floor for the real 116,352-row file — not the exact count, so the
# DAG still works against a future DE-SynPUF sample of similar size.
MIN_EXPECTED_ROWS = 100_000

BIGQUERY_TABLE_NAME = "beneficiary_summary"


def validate_dataframe(df: pd.DataFrame, min_expected_rows: int = MIN_EXPECTED_ROWS) -> dict:
    """Validate the raw beneficiary summary file. Raises ValueError on any failure."""
    missing_columns = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(f"Raw file missing expected columns: {sorted(missing_columns)}")

    if len(df) < min_expected_rows:
        raise ValueError(f"Raw file has {len(df)} rows, expected at least {min_expected_rows}")

    duplicate_ids = int(df["DESYNPUF_ID"].duplicated().sum())
    if duplicate_ids:
        raise ValueError(f"Raw file has {duplicate_ids} duplicate DESYNPUF_ID values")

    return {"row_count": len(df), "column_count": len(df.columns)}


def build_manifest_entry(file_path: Path, row_count: int) -> dict:
    """Compute a checksum manifest entry for the landed file.

    The checksum makes re-runs against an unchanged file detectable/auditable
    even though the downstream BigQuery load is idempotent regardless (full
    refresh, see `load_to_bigquery`).
    """
    checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return {
        "file": file_path.name,
        "sha256": checksum,
        "row_count": row_count,
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def load_to_bigquery(file_path: Path, project_id: str, dataset: str, expected_row_count: int) -> int:
    """Load the raw CSV into `{project_id}.{dataset}.beneficiary_summary`.

    Full refresh (WRITE_TRUNCATE) — idempotent and safe to re-run without
    duplicating rows or requiring incremental-load bookkeeping, appropriate
    for a static annual file (spec §12, hard constraint #6).

    Returns the resulting table's row count. Raises ValueError if it doesn't
    match `expected_row_count`.
    """
    from google.cloud import bigquery  # imported lazily: not needed for validate/land-only usage or unit tests

    client = bigquery.Client(project=project_id)
    dataset_ref = bigquery.DatasetReference(project_id, dataset)
    client.create_dataset(dataset_ref, exists_ok=True)

    table_ref = dataset_ref.table(BIGQUERY_TABLE_NAME)
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    with open(file_path, "rb") as source_file:
        load_job = client.load_table_from_file(source_file, table_ref, job_config=job_config)
    load_job.result()

    table = client.get_table(table_ref)
    if table.num_rows != expected_row_count:
        raise ValueError(
            f"BigQuery row count ({table.num_rows}) does not match validated raw row count ({expected_row_count})"
        )
    return table.num_rows
