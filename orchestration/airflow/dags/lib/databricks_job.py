"""Pure, framework-agnostic logic for triggering and polling the Databricks
`medicare_bronze_silver_gold` job (deployed by
spark_jobs/databricks/deploy.py — this module does not deploy it, only runs
it).

Kept separate from `dag_spark_bronze_silver.py` so it's unit-testable
without an Airflow environment — see
orchestration/airflow/tests/test_databricks_job.py. Raises plain
`ValueError`/`RuntimeError` on failure; the DAG task wrappers translate
that into `AirflowException`.
"""

from __future__ import annotations

import time

import requests

JOB_NAME = "medicare_bronze_silver_gold"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_job_id_by_name(host: str, token: str, name: str = JOB_NAME) -> int:
    resp = requests.get(f"{host}/api/2.2/jobs/list", headers=_headers(token), params={"name": name}, timeout=30)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    if not jobs:
        raise ValueError(
            f"No Databricks job named '{name}' found. Run `python spark_jobs/databricks/deploy.py` first."
        )
    return jobs[0]["job_id"]


def trigger_run(host: str, token: str, job_id: int) -> int:
    resp = requests.post(f"{host}/api/2.2/jobs/run-now", headers=_headers(token), json={"job_id": job_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()["run_id"]


def get_run_state(host: str, token: str, run_id: int) -> dict:
    resp = requests.get(
        f"{host}/api/2.2/jobs/runs/get", headers=_headers(token), params={"run_id": run_id}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()["state"]


def poll_run_until_terminal(
    host: str, token: str, run_id: int, poll_seconds: int = 15, timeout_seconds: int = 1800
) -> dict:
    """Blocks until the run reaches a terminal state. Raises RuntimeError on
    failure or timeout. Returns the final state dict on success.
    """
    elapsed = 0
    while elapsed < timeout_seconds:
        state = get_run_state(host, token, run_id)
        if state.get("life_cycle_state") == "TERMINATED":
            if state.get("result_state") != "SUCCESS":
                raise RuntimeError(f"Databricks run {run_id} failed: {state.get('state_message', '')}")
            return state
        if state.get("life_cycle_state") in ("INTERNAL_ERROR", "SKIPPED"):
            raise RuntimeError(f"Databricks run {run_id} did not complete: {state}")
        time.sleep(poll_seconds)
        elapsed += poll_seconds
    raise RuntimeError(f"Timed out after {timeout_seconds}s waiting for Databricks run {run_id}")
