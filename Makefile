.PHONY: setup sample-data profile ingest-test spark-test dbt-build streamlit-run airflow-up airflow-down airflow-logs clean

VENV := .venv
PYTHON := $(VENV)/bin/python

# --- Milestone 0 : Repository Foundation ---------------------------------

setup: ## Create the local venv and install dev tooling.
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip -q
	$(VENV)/bin/pip install -r requirements-dev.txt -q

sample-data: ## Regenerate the committed fixture sample from the raw CSV.
	$(PYTHON) scripts/generate_sample.py

profile: ## Execute the data profiling notebook against the full raw file.
	$(VENV)/bin/jupyter nbconvert --to notebook --execute --inplace \
		notebooks/00_data_profiling.ipynb \
		--ExecutePreprocessor.kernel_name=python3

# --- Milestone 1 : Airflow Ingestion --------------------------------------

ingest-test: ## Unit-test the ingestion DAG's validation/manifest logic (no Airflow needed).
	$(VENV)/bin/pytest orchestration/airflow/tests -v

# --- Later milestones (stubs until their milestone lands) ----------------

spark-test: ## Milestone 2: PySpark unit tests.
	@if [ -d spark_jobs/tests ]; then \
		$(VENV)/bin/pytest spark_jobs/tests; \
	else \
		echo "spark-test: Milestone 2 (PySpark Bronze/Silver) not yet implemented — see docs/IMPLEMENTATION_SPEC.md §28"; \
	fi

dbt-build: ## Milestone 4: dbt build against BigQuery.
	@if [ -d dbt/medicare_claims ]; then \
		cd dbt/medicare_claims && ../../$(VENV)/bin/dbt build; \
	else \
		echo "dbt-build: Milestone 4 (BigQuery + dbt) not yet implemented — see docs/IMPLEMENTATION_SPEC.md §28"; \
	fi

streamlit-run: ## Milestone 7: run the Streamlit exploration app locally.
	@if [ -f streamlit_app/app.py ]; then \
		$(VENV)/bin/streamlit run streamlit_app/app.py; \
	else \
		echo "streamlit-run: Milestone 7 (Streamlit Exploration App) not yet implemented — see docs/IMPLEMENTATION_SPEC.md §28"; \
	fi

airflow-up: ## Start local Airflow via Docker Compose (webserver at localhost:8081).
	docker compose up -d --build

airflow-down: ## Stop local Airflow.
	docker compose down

airflow-logs: ## Tail local Airflow scheduler/webserver logs.
	docker compose logs -f airflow-scheduler airflow-webserver

clean: ## Remove local venv and Python caches.
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
