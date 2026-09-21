"""Pure, framework-agnostic helpers for running a SQL statement against a
Databricks SQL Warehouse via the REST API (Statement Execution API).

Kept separate from `dag_gold_reconcile.py` for the same reason as
`databricks_job.py` — unit-testable without Airflow. See
orchestration/airflow/tests/test_gold_reconcile.py.
"""

from __future__ import annotations

import requests


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_first_warehouse_id(host: str, token: str) -> str:
    resp = requests.get(f"{host}/api/2.0/sql/warehouses", headers=_headers(token), timeout=30)
    resp.raise_for_status()
    warehouses = resp.json().get("warehouses", [])
    if not warehouses:
        raise ValueError("No SQL warehouse found in the Databricks workspace.")
    return warehouses[0]["id"]


def run_statement(host: str, token: str, warehouse_id: str, statement: str, wait_timeout: str = "30s") -> list:
    """Runs a SQL statement and returns its result rows (data_array).

    Raises RuntimeError if the statement doesn't succeed synchronously
    within `wait_timeout` (fine for the small aggregate queries this
    project runs — not built for long-running statements).
    """
    resp = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers=_headers(token),
        json={"statement": statement, "warehouse_id": warehouse_id, "wait_timeout": wait_timeout},
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()
    state = result.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise RuntimeError(f"Databricks SQL statement did not succeed (state={state}): {result.get('status')}")
    return result["result"]["data_array"]
