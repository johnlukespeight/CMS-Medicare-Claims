import os
import sys
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

# Make `transforms.beneficiary_transforms` importable the same way
# `spark_jobs/jobs/beneficiary_bronze_silver.py` imports it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Without this, PySpark's worker subprocesses fall back to whatever `python3`
# is first on PATH — which may not be this venv's interpreter (and PySpark
# refuses to run driver/worker on mismatched Python minor versions).
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CSV_PATH = REPO_ROOT / "data" / "samples" / "beneficiary_summary_sample.csv"


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    session = (
        SparkSession.builder.appName("beneficiary-transforms-tests")
        .master("local[2]")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    yield session
    session.stop()
