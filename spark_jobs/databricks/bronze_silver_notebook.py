# Databricks notebook source
# MAGIC %md
# MAGIC ## Milestone 3 — Bronze/Silver (Databricks Unity Catalog)
# MAGIC
# MAGIC Runs the *same* transform functions as Milestone 2
# MAGIC (`spark_jobs/transforms/beneficiary_transforms.py`), uploaded alongside this
# MAGIC notebook by `spark_jobs/databricks/deploy.py` — not a reimplementation.
# MAGIC Reads the raw CSV from a Unity Catalog Volume, writes governed Delta
# MAGIC tables under the `medicare` catalog (`bronze.beneficiary_summary`,
# MAGIC `silver.beneficiary`).
# MAGIC
# MAGIC See docs/IMPLEMENTATION_SPEC.md §7.2, §12, §28 (Milestone 3).

# COMMAND ----------

import sys

sys.path.insert(0, "__WORKSPACE_DIR__")
from beneficiary_transforms import RAW_SCHEMA, to_bronze, to_silver  # noqa: E402

# COMMAND ----------

dbutils.widgets.text("raw_csv_path", "/Volumes/medicare/bronze/raw_files/DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv")
raw_csv_path = dbutils.widgets.get("raw_csv_path")

# COMMAND ----------

raw_df = spark.read.csv(raw_csv_path, header=True, schema=RAW_SCHEMA)

bronze_df = to_bronze(raw_df)
bronze_df.write.format("delta").mode("overwrite").saveAsTable("medicare.bronze.beneficiary_summary")
print(f"Wrote {bronze_df.count():,} rows to medicare.bronze.beneficiary_summary")

# COMMAND ----------

silver_df = to_silver(bronze_df)
silver_df.write.format("delta").mode("overwrite").saveAsTable("medicare.silver.beneficiary")
print(f"Wrote {silver_df.count():,} rows to medicare.silver.beneficiary")
