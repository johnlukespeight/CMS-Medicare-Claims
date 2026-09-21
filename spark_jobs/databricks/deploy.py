"""Deploys Milestone 3's Databricks side: uploads the shared transform
module + driver notebook + gold SQL to the workspace, uploads the raw CSV
to a Unity Catalog Volume, and creates/updates the Databricks Job that ties
bronze -> silver -> gold together.

Idempotent — safe to re-run. Reads DATABRICKS_HOST/DATABRICKS_TOKEN from
.env (see docs/IMPLEMENTATION_SPEC.md §18).

Usage:
    python spark_jobs/databricks/deploy.py [--input data/raw/DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv]

This script does not run the job — orchestration/airflow/dags/dag_spark_bronze_silver.py
triggers it. Run `python spark_jobs/databricks/deploy.py --run` to also
trigger a run immediately, useful for verifying the deploy worked.
"""

from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")

DATABRICKS_HOST = os.environ["DATABRICKS_HOST"].rstrip("/")
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
HEADERS = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}

WORKSPACE_DIR = "/Workspace/Shared/medicare_claims"
CATALOG = "medicare"
VOLUME_PATH_PREFIX = f"/Volumes/{CATALOG}/bronze/raw_files"
JOB_NAME = "medicare_bronze_silver_gold"

LOCAL_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = REPO_ROOT / "data" / "raw" / "DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv"


def _api(method: str, path: str, **kwargs) -> requests.Response:
    resp = requests.request(method, f"{DATABRICKS_HOST}{path}", headers=HEADERS, **kwargs)
    resp.raise_for_status()
    return resp


def upload_workspace_file(local_path: Path, workspace_path: str, language: str | None = None) -> None:
    payload = {
        "path": workspace_path,
        "format": "SOURCE" if language else "AUTO",
        "content": base64.b64encode(local_path.read_bytes()).decode(),
        "overwrite": True,
    }
    if language:
        payload["language"] = language
    _api("POST", "/api/2.0/workspace/import", json=payload)
    print(f"  uploaded {workspace_path}")


def upload_to_volume(local_path: Path, volume_path: str) -> None:
    with open(local_path, "rb") as f:
        resp = requests.put(
            f"{DATABRICKS_HOST}/api/2.0/fs/files{volume_path}",
            headers=HEADERS,
            data=f,
            params={"overwrite": "true"},
        )
    resp.raise_for_status()
    print(f"  uploaded {local_path.name} -> {volume_path} ({local_path.stat().st_size:,} bytes)")


def get_serverless_warehouse_id() -> str:
    warehouses = _api("GET", "/api/2.0/sql/warehouses").json().get("warehouses", [])
    if not warehouses:
        raise RuntimeError(
            "No SQL warehouse found in this workspace — create one first (Free Edition ships one by default)."
        )
    warehouse = warehouses[0]
    print(f"  using SQL warehouse '{warehouse['name']}' ({warehouse['id']})")
    return warehouse["id"]


def find_existing_job_id(name: str) -> str | None:
    jobs = _api("GET", "/api/2.2/jobs/list", params={"name": name}).json().get("jobs", [])
    return jobs[0]["job_id"] if jobs else None


def deploy(input_csv: Path) -> int:
    print("Creating workspace directory...")
    _api("POST", "/api/2.0/workspace/mkdirs", json={"path": WORKSPACE_DIR})
    _api("POST", "/api/2.0/workspace/mkdirs", json={"path": f"{WORKSPACE_DIR}/sql"})

    print("Uploading transform module + driver notebook + gold SQL...")
    upload_workspace_file(
        REPO_ROOT / "spark_jobs" / "transforms" / "beneficiary_transforms.py",
        f"{WORKSPACE_DIR}/beneficiary_transforms.py",
    )

    notebook_source = (LOCAL_DIR / "bronze_silver_notebook.py").read_text().replace("__WORKSPACE_DIR__", WORKSPACE_DIR)
    payload = {
        "path": f"{WORKSPACE_DIR}/bronze_silver_notebook",
        "format": "SOURCE",
        "language": "PYTHON",
        "content": base64.b64encode(notebook_source.encode()).decode(),
        "overwrite": True,
    }
    _api("POST", "/api/2.0/workspace/import", json=payload)
    print(f"  uploaded {WORKSPACE_DIR}/bronze_silver_notebook")

    for sql_file in ["gold_beneficiary_cost_summary", "gold_chronic_condition_prevalence"]:
        # format=AUTO (no `language`) so this lands as a plain FILE object,
        # not a NOTEBOOK — sql_task.file.path needs a FILE. Passing
        # `language="SQL"` here silently uploads it as a SQL *notebook*
        # instead, which the SQL task type then fails to fetch.
        upload_workspace_file(LOCAL_DIR / "sql" / f"{sql_file}.sql", f"{WORKSPACE_DIR}/sql/{sql_file}.sql")

    print(f"Uploading raw CSV to Unity Catalog Volume ({VOLUME_PATH_PREFIX})...")
    volume_path = f"{VOLUME_PATH_PREFIX}/{input_csv.name}"
    upload_to_volume(input_csv, volume_path)

    print("Looking up SQL warehouse...")
    warehouse_id = get_serverless_warehouse_id()

    print(f"Creating/updating Databricks Job '{JOB_NAME}'...")
    job_settings = {
        "name": JOB_NAME,
        "tasks": [
            {
                "task_key": "bronze_silver",
                "notebook_task": {
                    "notebook_path": f"{WORKSPACE_DIR}/bronze_silver_notebook",
                    "base_parameters": {"raw_csv_path": volume_path},
                },
            },
            {
                "task_key": "gold_beneficiary_cost_summary",
                "depends_on": [{"task_key": "bronze_silver"}],
                "sql_task": {
                    "warehouse_id": warehouse_id,
                    "file": {"path": f"{WORKSPACE_DIR}/sql/gold_beneficiary_cost_summary.sql"},
                },
            },
            {
                "task_key": "gold_chronic_condition_prevalence",
                "depends_on": [{"task_key": "bronze_silver"}],
                "sql_task": {
                    "warehouse_id": warehouse_id,
                    "file": {"path": f"{WORKSPACE_DIR}/sql/gold_chronic_condition_prevalence.sql"},
                },
            },
        ],
    }

    existing_job_id = find_existing_job_id(JOB_NAME)
    if existing_job_id:
        _api("POST", "/api/2.2/jobs/reset", json={"job_id": existing_job_id, "new_settings": job_settings})
        print(f"  updated existing job (job_id={existing_job_id})")
        return existing_job_id
    else:
        job_id = _api("POST", "/api/2.2/jobs/create", json=job_settings).json()["job_id"]
        print(f"  created new job (job_id={job_id})")
        return job_id


def run_and_wait(job_id: int, poll_seconds: int = 10, timeout_seconds: int = 600) -> None:
    run_id = _api("POST", "/api/2.2/jobs/run-now", json={"job_id": job_id}).json()["run_id"]
    print(f"Triggered run_id={run_id}, polling...")
    elapsed = 0
    while elapsed < timeout_seconds:
        state = _api("GET", "/api/2.2/jobs/runs/get", params={"run_id": run_id}).json()["state"]
        life_cycle, result = state.get("life_cycle_state"), state.get("result_state")
        print(f"  {life_cycle} {result or ''}")
        if life_cycle == "TERMINATED":
            if result != "SUCCESS":
                raise SystemExit(f"Job run failed: {state.get('state_message', '')}")
            print("Run succeeded.")
            return
        time.sleep(poll_seconds)
        elapsed += poll_seconds
    raise SystemExit(f"Timed out after {timeout_seconds}s waiting for run {run_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run", action="store_true", help="Also trigger a run and wait for it to finish.")
    args = parser.parse_args()

    job_id = deploy(args.input)
    if args.run:
        run_and_wait(job_id)
