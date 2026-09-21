"""Milestone 3 — triggers the Databricks job that builds Unity Catalog's
bronze/silver/gold layers from the raw beneficiary file already uploaded to
a Unity Catalog Volume, and waits for it to complete.

This DAG does not deploy the job (that's spark_jobs/databricks/deploy.py,
run manually when the transform logic or SQL changes) — it only triggers
the existing job and polls it, mirroring dag_ingest_beneficiary_raw.py's
style. See docs/IMPLEMENTATION_SPEC.md §12, §28 (Milestone 3).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
from lib.databricks_job import JOB_NAME, get_job_id_by_name, poll_run_until_terminal, trigger_run

logger = logging.getLogger(__name__)


@dag(
    dag_id="dag_spark_bronze_silver",
    description="Trigger the Databricks Unity Catalog bronze/silver/gold job and wait for it",
    schedule=None,  # manually triggered, same as the ingestion DAG it follows
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["lakehouse", "milestone-3"],
    doc_md=__doc__,
)
def spark_bronze_silver():
    @task
    def trigger_databricks_run() -> int:
        host = os.environ.get("DATABRICKS_HOST")
        token = os.environ.get("DATABRICKS_TOKEN")
        if not host or not token:
            raise AirflowException(
                "DATABRICKS_HOST / DATABRICKS_TOKEN are not set — add Databricks workspace credentials "
                "to .env to run this task (see docs/IMPLEMENTATION_SPEC.md §18)."
            )
        try:
            job_id = get_job_id_by_name(host, token, JOB_NAME)
            run_id = trigger_run(host, token, job_id)
        except ValueError as exc:
            raise AirflowException(str(exc)) from exc

        logger.info("Triggered Databricks job_id=%s run_id=%s", job_id, run_id)
        return run_id

    @task
    def wait_for_completion(databricks_run_id: int) -> None:
        # Named `databricks_run_id`, not `run_id` — the latter collides with
        # Airflow's own reserved per-task context key of the same name.
        host = os.environ["DATABRICKS_HOST"]
        token = os.environ["DATABRICKS_TOKEN"]
        try:
            poll_run_until_terminal(host, token, databricks_run_id)
        except RuntimeError as exc:
            raise AirflowException(str(exc)) from exc
        logger.info("Databricks run %s succeeded", databricks_run_id)

    databricks_run_id = trigger_databricks_run()
    wait_for_completion(databricks_run_id)


spark_bronze_silver()
