"""Milestone 1 — validates the raw CMS DE-SynPUF Beneficiary Summary File,
lands it (checksum manifest), and loads it into BigQuery
`medicare_raw.beneficiary_summary` (full refresh, idempotent).

See docs/IMPLEMENTATION_SPEC.md §12 (pipeline stages) and §28 (Milestone 1).
Transformation/business logic must not live here — only orchestration. The
actual validation and load logic is in `lib/beneficiary_ingest.py`, kept
importable and unit-testable without Airflow.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException

from lib.beneficiary_ingest import build_manifest_entry, load_to_bigquery, validate_dataframe

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("AIRFLOW_DATA_DIR", "/opt/airflow/data"))
RAW_FILE_PATH = DATA_DIR / "raw" / "DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv"
MANIFEST_PATH = DATA_DIR / "raw" / "_ingest_manifest.json"


@dag(
    dag_id="dag_ingest_beneficiary_raw",
    description="Validate, land, and load the CMS DE-SynPUF beneficiary summary file into BigQuery",
    schedule=None,  # manually triggered — the source is a static annual CMS release, not a recurring feed
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "milestone-1"],
    doc_md=__doc__,
)
def ingest_beneficiary_raw():
    @task
    def validate_raw_csv() -> dict:
        import pandas as pd

        if not RAW_FILE_PATH.exists():
            raise AirflowException(
                f"Raw file not found at {RAW_FILE_PATH}. See docs/GOVERNANCE.md for sourcing the "
                "CMS DE-SynPUF file — it is gitignored and must be placed under data/raw/ manually."
            )

        df = pd.read_csv(RAW_FILE_PATH, dtype=str)
        try:
            result = validate_dataframe(df)
        except ValueError as exc:
            raise AirflowException(str(exc)) from exc

        logger.info("Validated %s rows, %s columns", result["row_count"], result["column_count"])
        return result

    @task
    def land_raw_file(validation: dict) -> dict:
        manifest_entry = build_manifest_entry(RAW_FILE_PATH, validation["row_count"])
        MANIFEST_PATH.write_text(json.dumps(manifest_entry, indent=2))
        logger.info("Landed raw file, checksum=%s", manifest_entry["sha256"])
        return manifest_entry

    @task
    def load_to_bigquery_task(manifest_entry: dict) -> None:
        project_id = os.environ.get("GCP_PROJECT_ID")
        dataset = os.environ.get("BQ_RAW_DATASET", "medicare_raw")

        if not project_id:
            raise AirflowException(
                "GCP_PROJECT_ID is not set — add GCP sandbox project credentials to .env to run this "
                "task (see docs/IMPLEMENTATION_SPEC.md §18). The validate/land steps above still ran "
                "and succeeded independently of this."
            )

        try:
            row_count = load_to_bigquery(RAW_FILE_PATH, project_id, dataset, manifest_entry["row_count"])
        except ValueError as exc:
            raise AirflowException(str(exc)) from exc

        logger.info("Loaded %s rows into %s.%s.beneficiary_summary", row_count, project_id, dataset)

    validation = validate_raw_csv()
    manifest_entry = land_raw_file(validation)
    load_to_bigquery_task(manifest_entry)


ingest_beneficiary_raw()
