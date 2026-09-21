from pathlib import Path

import pandas as pd
import pytest
from lib.beneficiary_ingest import EXPECTED_COLUMNS, build_manifest_entry, validate_dataframe

SAMPLE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "samples" / "beneficiary_summary_sample.csv"
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_PATH, dtype=str)


def test_validate_dataframe_accepts_the_real_fixture(sample_df):
    result = validate_dataframe(sample_df, min_expected_rows=100)
    assert result["row_count"] == len(sample_df)
    assert result["column_count"] == len(EXPECTED_COLUMNS)


def test_validate_dataframe_rejects_missing_column(sample_df):
    broken = sample_df.drop(columns=["BENE_DEATH_DT"])
    with pytest.raises(ValueError, match="missing expected columns"):
        validate_dataframe(broken, min_expected_rows=100)


def test_validate_dataframe_rejects_duplicate_beneficiary_id(sample_df):
    duplicated = pd.concat([sample_df, sample_df.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate DESYNPUF_ID"):
        validate_dataframe(duplicated, min_expected_rows=100)


def test_validate_dataframe_rejects_too_few_rows(sample_df):
    with pytest.raises(ValueError, match="expected at least"):
        validate_dataframe(sample_df, min_expected_rows=100_000)


def test_build_manifest_entry_has_expected_fields():
    entry = build_manifest_entry(SAMPLE_PATH, row_count=342)
    assert entry["file"] == "beneficiary_summary_sample.csv"
    assert entry["row_count"] == 342
    assert len(entry["sha256"]) == 64  # hex-encoded sha256
    assert "T" in entry["ingested_at"]  # ISO 8601 timestamp


def test_build_manifest_entry_checksum_is_deterministic():
    first = build_manifest_entry(SAMPLE_PATH, row_count=342)
    second = build_manifest_entry(SAMPLE_PATH, row_count=342)
    assert first["sha256"] == second["sha256"]
