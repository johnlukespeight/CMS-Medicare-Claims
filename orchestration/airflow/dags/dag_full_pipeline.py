"""Milestone 8 — the single entrypoint for a full, end-to-end pipeline run:
ingest -> (Databricks lakehouse + dbt/BigQuery warehouse, in parallel) ->
reconcile. Triggers and waits on each milestone's own DAG rather than
reimplementing their tasks, so each stays independently runnable/testable
(a fan-out/fan-in pattern: the lakehouse and warehouse paths don't actually
depend on each other's output, only on ingestion having landed the raw
file, so they run concurrently and reconcile joins them).

Prerequisite (not part of this DAG — a deploy-time step, not a per-run
data dependency): `make databricks-deploy` must have been run at least once
so the Databricks job and its Unity Catalog Volume file exist for
dag_spark_bronze_silver to trigger.

All four sub-DAGs must be unpaused for this to actually run (a paused
DAG's triggered runs sit in `queued` forever) — `make airflow-unpause-all`.

See docs/IMPLEMENTATION_SPEC.md §12, §28 (Milestone 8).
"""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

POKE_INTERVAL_SECONDS = 10

with DAG(
    dag_id="dag_full_pipeline",
    description="Full pipeline: ingest -> (Databricks + dbt in parallel) -> reconcile",
    schedule=None,  # manually triggered, same as every sub-DAG it runs
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["integrated-demo", "milestone-8"],
    doc_md=__doc__,
) as dag:
    run_ingest = TriggerDagRunOperator(
        task_id="run_ingest",
        trigger_dag_id="dag_ingest_beneficiary_raw",
        wait_for_completion=True,
        poke_interval=POKE_INTERVAL_SECONDS,
        reset_dag_run=True,
    )

    run_spark_bronze_silver = TriggerDagRunOperator(
        task_id="run_spark_bronze_silver",
        trigger_dag_id="dag_spark_bronze_silver",
        wait_for_completion=True,
        poke_interval=POKE_INTERVAL_SECONDS,
        reset_dag_run=True,
    )

    run_dbt_transform = TriggerDagRunOperator(
        task_id="run_dbt_transform",
        trigger_dag_id="dag_dbt_transform",
        wait_for_completion=True,
        poke_interval=POKE_INTERVAL_SECONDS,
        reset_dag_run=True,
    )

    run_gold_reconcile = TriggerDagRunOperator(
        task_id="run_gold_reconcile",
        trigger_dag_id="dag_gold_reconcile",
        wait_for_completion=True,
        poke_interval=POKE_INTERVAL_SECONDS,
        reset_dag_run=True,
    )

    run_ingest >> [run_spark_bronze_silver, run_dbt_transform] >> run_gold_reconcile
