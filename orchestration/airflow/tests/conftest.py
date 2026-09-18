import sys
from pathlib import Path

# Make `lib.beneficiary_ingest` importable the same way the DAG file imports
# it (Airflow puts the dags/ folder on sys.path; we replicate that here so
# these tests run without an Airflow installation).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dags"))
