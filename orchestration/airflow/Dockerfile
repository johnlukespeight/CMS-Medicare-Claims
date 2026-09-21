FROM apache/airflow:2.10.4-python3.11

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# dbt-core/dbt-bigquery live in their own venv, not Airflow's — installing
# them alongside Airflow's own dependencies produces real conflicts
# (protobuf 6.x vs. every google-cloud-* package pinning <6.0, pandas 3.x
# vs. apache-airflow-providers-google's <2.2 pin). See ADR-008. Triggered
# from a DAG via BashOperator calling /opt/dbt-venv/bin/dbt directly.
COPY dbt-requirements.txt /dbt-requirements.txt
USER root
RUN python -m venv /opt/dbt-venv && \
    chown -R airflow:root /opt/dbt-venv
USER airflow
RUN /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/dbt-venv/bin/pip install --no-cache-dir -r /dbt-requirements.txt
