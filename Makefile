.PHONY: setup setup-spark sample-data profile ingest-test spark-test spark-run databricks-deploy databricks-run dbt-seed dbt-build dbt-docs streamlit-test streamlit-run streamlit-run-bigquery airflow-up airflow-down airflow-logs clean

VENV := .venv
PYTHON := $(VENV)/bin/python

# PySpark needs Java 8/11/17 and (as of this writing) Python <=3.13 — kept
# in a separate venv/JDK from the main tooling above, which uses whatever
# `python3` resolves to. `brew install openjdk@17` if this path doesn't exist.
SPARK_VENV := .venv-spark
JAVA_HOME := $(shell brew --prefix openjdk@17 2>/dev/null)/libexec/openjdk.jdk/Contents/Home

# --- Milestone 0 : Repository Foundation ---------------------------------

setup: ## Create the local venv and install dev tooling.
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip -q
	$(VENV)/bin/pip install -r requirements-dev.txt -q
	$(VENV)/bin/pip install -r spark_jobs/databricks/requirements.txt -q
	$(VENV)/bin/pip install -r dbt/requirements.txt -q
	$(VENV)/bin/pip install -r streamlit_app/requirements.txt -q

sample-data: ## Regenerate the committed fixture sample from the raw CSV.
	$(PYTHON) scripts/generate_sample.py

profile: ## Execute the data profiling notebook against the full raw file.
	$(VENV)/bin/jupyter nbconvert --to notebook --execute --inplace \
		notebooks/00_data_profiling.ipynb \
		--ExecutePreprocessor.kernel_name=python3

# --- Milestone 1 : Airflow Ingestion --------------------------------------

ingest-test: ## Unit-test the ingestion DAG's validation/manifest logic (no Airflow needed).
	$(VENV)/bin/pytest orchestration/airflow/tests -v

# --- Milestone 2 : PySpark Bronze/Silver ----------------------------------

setup-spark: ## Create the dedicated PySpark venv (Python 3.13, separate from $(VENV)).
	python3.13 -m venv $(SPARK_VENV)
	$(SPARK_VENV)/bin/pip install --upgrade pip -q
	$(SPARK_VENV)/bin/pip install -r spark_jobs/requirements.txt -q

spark-test: ## Unit-test the bronze/silver transform logic.
	JAVA_HOME=$(JAVA_HOME) $(SPARK_VENV)/bin/pytest spark_jobs/tests -v

spark-run: ## Run the bronze/silver job locally (defaults to the fixture sample).
	JAVA_HOME=$(JAVA_HOME) $(SPARK_VENV)/bin/python spark_jobs/jobs/beneficiary_bronze_silver.py

# --- Milestone 3 : Databricks Unity Catalog -------------------------------

databricks-deploy: ## Upload transforms/notebook/gold SQL + raw CSV, create/update the Databricks Job.
	$(PYTHON) spark_jobs/databricks/deploy.py

databricks-run: ## Deploy, then trigger the Databricks job and wait for it to finish.
	$(PYTHON) spark_jobs/databricks/deploy.py --run

# --- Milestone 4 : BigQuery + dbt ------------------------------------------
# env_var() in profiles.yml/dbt_project.yml reads the shell environment, not
# .env directly, so these targets source .env first.

DBT := ../../$(VENV)/bin/dbt
# GOOGLE_APPLICATION_CREDENTIALS in .env is relative to the repo root (as
# used by spark_jobs/databricks/deploy.py etc.) — re-exported as absolute
# here since these targets `cd` into dbt/medicare_claims first.
LOAD_ENV := set -a; . ../../.env; export GOOGLE_APPLICATION_CREDENTIALS=$(CURDIR)/secrets/gcp-service-account.json; set +a;

dbt-seed: ## Load the ssa_state_codes reference seed into BigQuery.
	cd dbt/medicare_claims && $(LOAD_ENV) $(DBT) seed

dbt-build: ## Run all dbt models + tests against the BigQuery sandbox project.
	cd dbt/medicare_claims && $(LOAD_ENV) $(DBT) build

dbt-docs: ## Generate and serve the dbt docs lineage graph (localhost:8082).
	cd dbt/medicare_claims && $(LOAD_ENV) $(DBT) docs generate && $(DBT) docs serve --port 8082

# --- Milestone 7 : Streamlit Exploration App --------------------------------

streamlit-test: ## Unit-test the data-access layer (DuckDB backend, no cloud needed).
	$(VENV)/bin/pytest streamlit_app/tests -v

streamlit-run: ## Run the app locally against the fixture sample (STREAMLIT_BACKEND=duckdb, zero cloud cost).
	STREAMLIT_BACKEND=duckdb $(VENV)/bin/streamlit run streamlit_app/app.py

streamlit-run-bigquery: ## Run the app against the live BigQuery sandbox project.
	STREAMLIT_BACKEND=bigquery $(VENV)/bin/streamlit run streamlit_app/app.py

# --- Later milestones (stubs until their milestone lands) ----------------

airflow-up: ## Start local Airflow via Docker Compose (webserver at localhost:8081).
	docker compose up -d --build

airflow-down: ## Stop local Airflow.
	docker compose down

airflow-logs: ## Tail local Airflow scheduler/webserver logs.
	docker compose logs -f airflow-scheduler airflow-webserver

clean: ## Remove local venvs and Python caches.
	rm -rf $(VENV) $(SPARK_VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
