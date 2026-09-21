from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from data_access import BENEFICIARY_COLUMNS, CONDITION_COLUMNS, SAMPLE_CSV_PATH, load_beneficiary_gold


@pytest.fixture(scope="module")
def duckdb_df() -> pd.DataFrame:
    return load_beneficiary_gold(backend="duckdb")


def test_duckdb_backend_returns_expected_shape(duckdb_df):
    raw = pd.read_csv(SAMPLE_CSV_PATH, dtype=str)
    assert len(duckdb_df) == len(raw)
    assert list(duckdb_df.columns) == BENEFICIARY_COLUMNS


def test_duckdb_backend_deceased_count_matches_raw_file(duckdb_df):
    raw = pd.read_csv(SAMPLE_CSV_PATH, dtype=str)
    expected_deceased = raw["BENE_DEATH_DT"].notna().sum()
    assert duckdb_df["is_deceased"].sum() == expected_deceased


def test_duckdb_backend_age_bands_are_valid(duckdb_df):
    assert set(duckdb_df["age_band"].unique()) <= {"Under 65", "65-74", "75-84", "85+"}


def test_duckdb_backend_matches_hand_computed_row(duckdb_df):
    # Cross-checks the first raw row against its own raw values, rather than
    # a hardcoded expectation -- robust to the fixture being regenerated.
    raw = pd.read_csv(SAMPLE_CSV_PATH, dtype=str)
    raw_row = raw.iloc[0]
    result_row = duckdb_df[duckdb_df["desynpuf_id"] == raw_row["DESYNPUF_ID"]].iloc[0]

    condition_raw_cols = [
        "SP_ALZHDMTA",
        "SP_CHF",
        "SP_CHRNKIDN",
        "SP_CNCR",
        "SP_COPD",
        "SP_DEPRESSN",
        "SP_DIABETES",
        "SP_ISCHMCHT",
        "SP_OSTEOPRS",
        "SP_RA_OA",
        "SP_STRKETIA",
    ]
    expected_count = sum(raw_row[c] == "1" for c in condition_raw_cols)
    assert result_row["chronic_condition_count"] == expected_count

    expected_cost = float(raw_row["MEDREIMB_IP"]) + float(raw_row["MEDREIMB_OP"]) + float(raw_row["MEDREIMB_CAR"])
    assert result_row["total_medicare_reimbursement"] == pytest.approx(expected_cost)

    expected_deceased = pd.notna(raw_row["BENE_DEATH_DT"])
    assert bool(result_row["is_deceased"]) == expected_deceased


def test_load_beneficiary_gold_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unknown STREAMLIT_BACKEND"):
        load_beneficiary_gold(backend="snowflake")


def test_load_beneficiary_gold_reads_env_var_when_backend_not_passed(monkeypatch):
    monkeypatch.setenv("STREAMLIT_BACKEND", "duckdb")
    df = load_beneficiary_gold()
    assert not df.empty


def test_bigquery_backend_builds_expected_query_and_returns_dataframe(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("BQ_MARTS_DATASET", "medicare_marts")
    monkeypatch.setenv("BQ_STAGING_DATASET", "medicare_staging")

    fake_df = pd.DataFrame({col: [] for col in BENEFICIARY_COLUMNS})
    fake_query_job = MagicMock()
    fake_query_job.to_dataframe.return_value = fake_df
    fake_client = MagicMock()
    fake_client.query.return_value = fake_query_job

    with patch("google.cloud.bigquery.Client", return_value=fake_client):
        result = load_beneficiary_gold(backend="bigquery")

    assert result is fake_df
    called_query = fake_client.query.call_args[0][0]
    assert "my-project.medicare_marts.dim_beneficiary" in called_query
    assert "my-project.medicare_marts.fct_beneficiary_annual_cost" in called_query
    assert "my-project.medicare_staging.stg_beneficiary_summary" in called_query
    for col in CONDITION_COLUMNS:
        assert f"stg.{col}" in called_query
