"""Runnable Milestone 2 job: raw CSV -> bronze -> silver, written as local
Delta tables.

This runs against a local SparkSession with the `delta-spark` pip package —
good enough to prove the transform logic end to end without a cluster.
Milestone 3 ports the same transform functions
(spark_jobs/transforms/beneficiary_transforms.py) to a real Databricks job
writing to Unity Catalog managed tables; this script is not that job.

Usage:
    python spark_jobs/jobs/beneficiary_bronze_silver.py \
        --input data/samples/beneficiary_summary_sample.csv \
        --bronze-output data/lakehouse/bronze/beneficiary_summary \
        --silver-output data/lakehouse/silver/beneficiary

Defaults to the committed fixture sample so it's runnable with no setup
beyond `pip install -r spark_jobs/requirements.txt`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from transforms.beneficiary_transforms import RAW_SCHEMA, to_bronze, to_silver  # noqa: E402

# See spark_jobs/tests/conftest.py for why this matters — without it, worker
# subprocesses can pick up a different Python than the driver.
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT = REPO_ROOT / "data" / "samples" / "beneficiary_summary_sample.csv"
DEFAULT_BRONZE_OUTPUT = REPO_ROOT / "data" / "lakehouse" / "bronze" / "beneficiary_summary"
DEFAULT_SILVER_OUTPUT = REPO_ROOT / "data" / "lakehouse" / "silver" / "beneficiary"


def build_spark_session(app_name: str = "beneficiary_bronze_silver") -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def run(input_path: Path, bronze_output: Path, silver_output: Path) -> None:
    spark = build_spark_session()
    try:
        raw_df = spark.read.csv(str(input_path), header=True, schema=RAW_SCHEMA)

        bronze_df = to_bronze(raw_df)
        bronze_df.write.format("delta").mode("overwrite").save(str(bronze_output))
        print(f"Wrote {bronze_df.count():,} bronze rows to {bronze_output}")

        silver_df = to_silver(bronze_df)
        silver_df.write.format("delta").mode("overwrite").save(str(silver_output))
        print(f"Wrote {silver_df.count():,} silver rows to {silver_output}")

        print("\nSample silver rows:")
        silver_df.select(
            "DESYNPUF_ID",
            "age_2008",
            "age_band",
            "is_deceased",
            "state_abbr",
            "chronic_condition_count",
        ).show(5, truncate=False)
    finally:
        spark.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--bronze-output", type=Path, default=DEFAULT_BRONZE_OUTPUT)
    parser.add_argument("--silver-output", type=Path, default=DEFAULT_SILVER_OUTPUT)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.bronze_output, args.silver_output)
