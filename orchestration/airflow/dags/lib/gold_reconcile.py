"""Pure, framework-agnostic logic for comparing the Databricks and BigQuery
gold layers (Milestone 5 — docs/IMPLEMENTATION_SPEC.md §12, §28).

Kept separate from `dag_gold_reconcile.py` so it's unit-testable without an
Airflow environment — see
orchestration/airflow/tests/test_gold_reconcile.py. Raises plain
`ValueError` on mismatch; the DAG task wrapper translates that into
`AirflowException`.
"""

from __future__ import annotations

from lib.databricks_sql import get_first_warehouse_id, run_statement

METRICS_QUERY = "SELECT COUNT(*), SUM(total_medicare_reimbursement) FROM {table}"

# Both pipelines are derived from the identical raw file and should match
# to the penny -- confirmed empirically (both report exactly
# $465,233,840.00 as of this writing) -- but a small tolerance is still
# used rather than exact float equality, standard defensive practice for
# cross-engine sum comparisons.
DEFAULT_COST_TOLERANCE = 1.00


def get_databricks_gold_metrics(host: str, token: str) -> dict:
    warehouse_id = get_first_warehouse_id(host, token)
    rows = run_statement(
        host, token, warehouse_id, METRICS_QUERY.format(table="medicare.gold.beneficiary_cost_summary")
    )
    count, total = rows[0]
    return {"beneficiary_count": int(count), "total_medicare_reimbursement": float(total)}


def get_bigquery_gold_metrics(project_id: str, dataset: str) -> dict:
    from google.cloud import bigquery  # imported lazily -- not needed for unit tests

    client = bigquery.Client(project=project_id)
    query = METRICS_QUERY.format(table=f"`{project_id}.{dataset}.fct_beneficiary_annual_cost`")
    row = next(iter(client.query(query).result()))
    count, total = row[0], row[1]
    return {"beneficiary_count": int(count), "total_medicare_reimbursement": float(total)}


def compare_gold_metrics(
    databricks_metrics: dict, bigquery_metrics: dict, cost_tolerance: float = DEFAULT_COST_TOLERANCE
) -> dict:
    """Raises ValueError describing every mismatch found. Returns the
    agreed-upon metrics on success.
    """
    mismatches = []

    if databricks_metrics["beneficiary_count"] != bigquery_metrics["beneficiary_count"]:
        mismatches.append(
            f"beneficiary_count mismatch: Databricks={databricks_metrics['beneficiary_count']} "
            f"BigQuery={bigquery_metrics['beneficiary_count']}"
        )

    cost_diff = abs(
        databricks_metrics["total_medicare_reimbursement"] - bigquery_metrics["total_medicare_reimbursement"]
    )
    if cost_diff > cost_tolerance:
        mismatches.append(
            "total_medicare_reimbursement mismatch: "
            f"Databricks={databricks_metrics['total_medicare_reimbursement']:.2f} "
            f"BigQuery={bigquery_metrics['total_medicare_reimbursement']:.2f} "
            f"(diff={cost_diff:.2f}, tolerance={cost_tolerance})"
        )

    if mismatches:
        raise ValueError("Gold layer reconciliation failed:\n" + "\n".join(mismatches))

    return {
        "beneficiary_count": databricks_metrics["beneficiary_count"],
        "total_medicare_reimbursement": databricks_metrics["total_medicare_reimbursement"],
    }
