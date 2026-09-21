"""Milestone 4 — runs `dbt build` (seed + staging/intermediate/marts models
+ tests, all in dependency order) against BigQuery.

dbt runs from a separate venv (/opt/dbt-venv, baked into the Airflow image
by orchestration/airflow/Dockerfile) rather than Airflow's own Python
environment — installing dbt-core/dbt-bigquery alongside Airflow's own
dependencies produces real conflicts (protobuf 6.x vs. every google-cloud-*
package pinning <6.0, pandas 3.x vs. apache-airflow-providers-google's <2.2
pin), confirmed by actually trying it. See ADR-008.

See docs/IMPLEMENTATION_SPEC.md §12, §28 (Milestone 4).
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task

DBT_PROJECT_DIR = "/opt/airflow/dbt/medicare_claims"
DBT_BIN = "/opt/dbt-venv/bin/dbt"


@dag(
    dag_id="dag_dbt_transform",
    description="Run dbt build (seed + staging/intermediate/marts + tests) against BigQuery",
    schedule=None,  # manually triggered, after dag_ingest_beneficiary_raw
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "milestone-4"],
    doc_md=__doc__,
)
def dbt_transform():
    @task.bash
    def dbt_build() -> str:
        return f"{DBT_BIN} build --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"

    dbt_build()


dbt_transform()
