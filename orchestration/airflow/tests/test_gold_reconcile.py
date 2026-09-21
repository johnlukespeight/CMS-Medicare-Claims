from unittest.mock import MagicMock, patch

import pytest
from lib.gold_reconcile import compare_gold_metrics, get_bigquery_gold_metrics, get_databricks_gold_metrics


def test_compare_gold_metrics_passes_on_exact_match():
    databricks = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    bigquery = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    agreed = compare_gold_metrics(databricks, bigquery)
    assert agreed == databricks


def test_compare_gold_metrics_passes_within_tolerance():
    databricks = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.00}
    bigquery = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.50}
    compare_gold_metrics(databricks, bigquery, cost_tolerance=1.00)


def test_compare_gold_metrics_raises_on_beneficiary_count_mismatch():
    databricks = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    bigquery = {"beneficiary_count": 116351, "total_medicare_reimbursement": 465233840.0}
    with pytest.raises(ValueError, match="beneficiary_count mismatch"):
        compare_gold_metrics(databricks, bigquery)


def test_compare_gold_metrics_raises_on_cost_mismatch_beyond_tolerance():
    databricks = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    bigquery = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233900.0}
    with pytest.raises(ValueError, match="total_medicare_reimbursement mismatch"):
        compare_gold_metrics(databricks, bigquery, cost_tolerance=1.00)


def test_compare_gold_metrics_reports_both_mismatches_together():
    databricks = {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    bigquery = {"beneficiary_count": 1, "total_medicare_reimbursement": 1.0}
    with pytest.raises(ValueError) as exc_info:
        compare_gold_metrics(databricks, bigquery)
    assert "beneficiary_count mismatch" in str(exc_info.value)
    assert "total_medicare_reimbursement mismatch" in str(exc_info.value)


@patch("lib.gold_reconcile.run_statement")
@patch("lib.gold_reconcile.get_first_warehouse_id")
def test_get_databricks_gold_metrics_parses_result_row(mock_get_warehouse, mock_run_statement):
    mock_get_warehouse.return_value = "wh123"
    mock_run_statement.return_value = [["116352", "465233840.0"]]
    metrics = get_databricks_gold_metrics("https://example.databricks.com", "token")
    assert metrics == {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    mock_run_statement.assert_called_once()
    assert "medicare.gold.beneficiary_cost_summary" in mock_run_statement.call_args[0][3]


def test_get_bigquery_gold_metrics_parses_result_row():
    fake_row = [116352, 465233840.0]
    fake_result = MagicMock()
    fake_result.result.return_value = iter([fake_row])
    fake_client = MagicMock()
    fake_client.query.return_value = fake_result

    with patch("google.cloud.bigquery.Client", return_value=fake_client):
        metrics = get_bigquery_gold_metrics("my-project", "medicare_marts")

    assert metrics == {"beneficiary_count": 116352, "total_medicare_reimbursement": 465233840.0}
    called_query = fake_client.query.call_args[0][0]
    assert "my-project.medicare_marts.fct_beneficiary_annual_cost" in called_query
