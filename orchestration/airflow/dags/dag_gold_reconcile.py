"""Milestone 5 — compares the Databricks gold layer
(`medicare.gold.beneficiary_cost_summary`) against the BigQuery gold layer
(`fct_beneficiary_annual_cost`): beneficiary count and total Medicare
reimbursement must agree (within a small dollar tolerance for cross-engine
float summation — see lib/gold_reconcile.py). Fails loudly on a mismatch.

Run dag_spark_bronze_silver and dag_dbt_transform first — this DAG only
reads their output, it doesn't trigger them.

See docs/IMPLEMENTATION_SPEC.md §12, §28 (Milestone 5).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException

from lib.gold_reconcile import compare_gold_metrics, get_bigquery_gold_metrics, get_databricks_gold_metrics

logger = logging.getLogger(__name__)


@dag(
    dag_id="dag_gold_reconcile",
    description="Cross-check Databricks and BigQuery gold-layer totals",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["reconciliation", "milestone-5"],
    doc_md=__doc__,
)
def gold_reconcile():
    @task
    def fetch_databricks_metrics() -> dict:
        host = os.environ.get("DATABRICKS_HOST")
        token = os.environ.get("DATABRICKS_TOKEN")
        if not host or not token:
            raise AirflowException(
                "DATABRICKS_HOST / DATABRICKS_TOKEN are not set — see docs/IMPLEMENTATION_SPEC.md §18."
            )
        metrics = get_databricks_gold_metrics(host, token)
        logger.info("Databricks gold metrics: %s", metrics)
        return metrics

    @task
    def fetch_bigquery_metrics() -> dict:
        project_id = os.environ.get("GCP_PROJECT_ID")
        dataset = os.environ.get("BQ_MARTS_DATASET", "medicare_marts")
        if not project_id:
            raise AirflowException("GCP_PROJECT_ID is not set — see docs/IMPLEMENTATION_SPEC.md §18.")
        metrics = get_bigquery_gold_metrics(project_id, dataset)
        logger.info("BigQuery gold metrics: %s", metrics)
        return metrics

    @task
    def reconcile(databricks_metrics: dict, bigquery_metrics: dict) -> None:
        try:
            agreed = compare_gold_metrics(databricks_metrics, bigquery_metrics)
        except ValueError as exc:
            raise AirflowException(str(exc)) from exc
        logger.info("Reconciled: %s", agreed)

    reconcile(fetch_databricks_metrics(), fetch_bigquery_metrics())


gold_reconcile()
