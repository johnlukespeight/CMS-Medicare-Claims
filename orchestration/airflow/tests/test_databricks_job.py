from unittest.mock import MagicMock, patch

import pytest
from lib.databricks_job import get_job_id_by_name, poll_run_until_terminal, trigger_run

HOST = "https://example.cloud.databricks.com"
TOKEN = "fake-token"


def _mock_response(json_body: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


@patch("lib.databricks_job.requests.get")
def test_get_job_id_by_name_returns_id(mock_get):
    mock_get.return_value = _mock_response({"jobs": [{"job_id": 42}]})
    assert get_job_id_by_name(HOST, TOKEN, "medicare_bronze_silver_gold") == 42


@patch("lib.databricks_job.requests.get")
def test_get_job_id_by_name_raises_when_not_found(mock_get):
    mock_get.return_value = _mock_response({"jobs": []})
    with pytest.raises(ValueError, match="No Databricks job named"):
        get_job_id_by_name(HOST, TOKEN, "does_not_exist")


@patch("lib.databricks_job.requests.post")
def test_trigger_run_returns_run_id(mock_post):
    mock_post.return_value = _mock_response({"run_id": 999})
    assert trigger_run(HOST, TOKEN, job_id=42) == 999


@patch("lib.databricks_job.time.sleep", return_value=None)
@patch("lib.databricks_job.get_run_state")
def test_poll_run_until_terminal_returns_state_on_success(mock_get_state, _mock_sleep):
    mock_get_state.side_effect = [
        {"life_cycle_state": "RUNNING"},
        {"life_cycle_state": "TERMINATED", "result_state": "SUCCESS"},
    ]
    state = poll_run_until_terminal(HOST, TOKEN, run_id=999, poll_seconds=0)
    assert state["result_state"] == "SUCCESS"


@patch("lib.databricks_job.time.sleep", return_value=None)
@patch("lib.databricks_job.get_run_state")
def test_poll_run_until_terminal_raises_on_failure(mock_get_state, _mock_sleep):
    mock_get_state.return_value = {
        "life_cycle_state": "TERMINATED",
        "result_state": "FAILED",
        "state_message": "boom",
    }
    with pytest.raises(RuntimeError, match="boom"):
        poll_run_until_terminal(HOST, TOKEN, run_id=999, poll_seconds=0)


@patch("lib.databricks_job.time.sleep", return_value=None)
@patch("lib.databricks_job.get_run_state")
def test_poll_run_until_terminal_raises_on_timeout(mock_get_state, _mock_sleep):
    mock_get_state.return_value = {"life_cycle_state": "RUNNING"}
    with pytest.raises(RuntimeError, match="Timed out"):
        poll_run_until_terminal(HOST, TOKEN, run_id=999, poll_seconds=1, timeout_seconds=2)
