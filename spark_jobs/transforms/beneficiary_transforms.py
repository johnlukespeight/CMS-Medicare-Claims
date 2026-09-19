"""Bronze/silver transformation logic for the CMS DE-SynPUF beneficiary
summary file (docs/IMPLEMENTATION_SPEC.md §7.2, §8, §14).

Pure functions over Spark DataFrames — no I/O, no SparkSession creation —
so they're unit-testable in isolation (spark_jobs/tests/) and reusable from
`spark_jobs/jobs/beneficiary_bronze_silver.py`, the runnable job.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, IntegerType, StringType, StructField, StructType

# Raw CMS DE-SynPUF schema (docs/IMPLEMENTATION_SPEC.md §7.1). All source
# columns arrive as strings; bronze casts each to its correct type and
# nothing else — no business logic.
RAW_SCHEMA = StructType(
    [
        StructField("DESYNPUF_ID", StringType()),
        StructField("BENE_BIRTH_DT", StringType()),
        StructField("BENE_DEATH_DT", StringType()),
        StructField("BENE_SEX_IDENT_CD", StringType()),
        StructField("BENE_RACE_CD", StringType()),
        StructField("BENE_ESRD_IND", StringType()),
        StructField("SP_STATE_CODE", StringType()),
        StructField("BENE_COUNTY_CD", StringType()),
        StructField("BENE_HI_CVRAGE_TOT_MONS", StringType()),
        StructField("BENE_SMI_CVRAGE_TOT_MONS", StringType()),
        StructField("BENE_HMO_CVRAGE_TOT_MONS", StringType()),
        StructField("PLAN_CVRG_MOS_NUM", StringType()),
        StructField("SP_ALZHDMTA", StringType()),
        StructField("SP_CHF", StringType()),
        StructField("SP_CHRNKIDN", StringType()),
        StructField("SP_CNCR", StringType()),
        StructField("SP_COPD", StringType()),
        StructField("SP_DEPRESSN", StringType()),
        StructField("SP_DIABETES", StringType()),
        StructField("SP_ISCHMCHT", StringType()),
        StructField("SP_OSTEOPRS", StringType()),
        StructField("SP_RA_OA", StringType()),
        StructField("SP_STRKETIA", StringType()),
        StructField("MEDREIMB_IP", StringType()),
        StructField("BENRES_IP", StringType()),
        StructField("PPPYMT_IP", StringType()),
        StructField("MEDREIMB_OP", StringType()),
        StructField("BENRES_OP", StringType()),
        StructField("PPPYMT_OP", StringType()),
        StructField("MEDREIMB_CAR", StringType()),
        StructField("BENRES_CAR", StringType()),
        StructField("PPPYMT_CAR", StringType()),
    ]
)

_DATE_COLUMNS = ["BENE_BIRTH_DT", "BENE_DEATH_DT"]
_INT_COLUMNS = [
    "BENE_HI_CVRAGE_TOT_MONS",
    "BENE_SMI_CVRAGE_TOT_MONS",
    "BENE_HMO_CVRAGE_TOT_MONS",
    "PLAN_CVRG_MOS_NUM",
]
# Not clipped, not filtered — negative values are real claim adjustments,
# see docs/IMPLEMENTATION_SPEC.md §8.
_MONEY_COLUMNS = [
    "MEDREIMB_IP",
    "BENRES_IP",
    "PPPYMT_IP",
    "MEDREIMB_OP",
    "BENRES_OP",
    "PPPYMT_OP",
    "MEDREIMB_CAR",
    "BENRES_CAR",
    "PPPYMT_CAR",
]

# CMS DE-SynPUF Codebook (BEN-7, SP_STATE_CODE) — the SSA state-code system,
# not FIPS. Verified against the official CMS codebook, not guessed: codes
# 40 and 48 are intentionally absent, and 54 is CMS's own coarsened
# "Other/Territory" bucket (Puerto Rico, Virgin Islands, foreign addresses,
# disclosure-suppressed values) — not a real US state.
SSA_STATE_CODE_TO_STATE = {
    "01": ("AL", "Alabama"),
    "02": ("AK", "Alaska"),
    "03": ("AZ", "Arizona"),
    "04": ("AR", "Arkansas"),
    "05": ("CA", "California"),
    "06": ("CO", "Colorado"),
    "07": ("CT", "Connecticut"),
    "08": ("DE", "Delaware"),
    "09": ("DC", "District of Columbia"),
    "10": ("FL", "Florida"),
    "11": ("GA", "Georgia"),
    "12": ("HI", "Hawaii"),
    "13": ("ID", "Idaho"),
    "14": ("IL", "Illinois"),
    "15": ("IN", "Indiana"),
    "16": ("IA", "Iowa"),
    "17": ("KS", "Kansas"),
    "18": ("KY", "Kentucky"),
    "19": ("LA", "Louisiana"),
    "20": ("ME", "Maine"),
    "21": ("MD", "Maryland"),
    "22": ("MA", "Massachusetts"),
    "23": ("MI", "Michigan"),
    "24": ("MN", "Minnesota"),
    "25": ("MS", "Mississippi"),
    "26": ("MO", "Missouri"),
    "27": ("MT", "Montana"),
    "28": ("NE", "Nebraska"),
    "29": ("NV", "Nevada"),
    "30": ("NH", "New Hampshire"),
    "31": ("NJ", "New Jersey"),
    "32": ("NM", "New Mexico"),
    "33": ("NY", "New York"),
    "34": ("NC", "North Carolina"),
    "35": ("ND", "North Dakota"),
    "36": ("OH", "Ohio"),
    "37": ("OK", "Oklahoma"),
    "38": ("OR", "Oregon"),
    "39": ("PA", "Pennsylvania"),
    "41": ("RI", "Rhode Island"),
    "42": ("SC", "South Carolina"),
    "43": ("SD", "South Dakota"),
    "44": ("TN", "Tennessee"),
    "45": ("TX", "Texas"),
    "46": ("UT", "Utah"),
    "47": ("VT", "Vermont"),
    "49": ("VA", "Virginia"),
    "50": ("WA", "Washington"),
    "51": ("WV", "West Virginia"),
    "52": ("WI", "Wisconsin"),
    "53": ("WY", "Wyoming"),
    "54": ("OTHER", "Other/Territory"),
}

# CMS codebook: SP_* = "1" means the condition is present, "2" means absent.
CHRONIC_CONDITION_COLUMNS = {
    "SP_ALZHDMTA": "has_alzheimers",
    "SP_CHF": "has_chf",
    "SP_CHRNKIDN": "has_chronic_kidney_disease",
    "SP_CNCR": "has_cancer",
    "SP_COPD": "has_copd",
    "SP_DEPRESSN": "has_depression",
    "SP_DIABETES": "has_diabetes",
    "SP_ISCHMCHT": "has_ischemic_heart_disease",
    "SP_OSTEOPRS": "has_osteoporosis",
    "SP_RA_OA": "has_rheumatoid_or_osteoarthritis",
    "SP_STRKETIA": "has_stroke_or_tia",
}

REFERENCE_DATE = "2008-12-31"


def to_bronze(raw_df: DataFrame) -> DataFrame:
    """Cast raw CMS columns to their correct types. No business logic.

    Adds `_ingested_at` (current timestamp). Grain: one row per DESYNPUF_ID,
    matching the source file (not enforced here — see `to_silver`'s dedup).
    """
    df = raw_df
    for col_name in _DATE_COLUMNS:
        df = df.withColumn(col_name, F.to_date(F.col(col_name), "yyyyMMdd"))
    for col_name in _INT_COLUMNS:
        df = df.withColumn(col_name, F.col(col_name).cast(IntegerType()))
    for col_name in _MONEY_COLUMNS:
        df = df.withColumn(col_name, F.col(col_name).cast(DoubleType()))
    return df.withColumn("_ingested_at", F.current_timestamp())


def _state_lookup_column(ssa_code_col: Column, index: int) -> Column:
    """Build a `CASE WHEN` expression mapping an SSA state code to its
    abbreviation (index 0) or full name (index 1). A small, static,
    project-owned lookup — not worth a join for 52 rows.
    """
    mapping = F.create_map(
        *[item for code, pair in SSA_STATE_CODE_TO_STATE.items() for item in (F.lit(code), F.lit(pair[index]))]
    )
    return mapping[ssa_code_col]


def to_silver(bronze_df: DataFrame) -> DataFrame:
    """Clean, dedupe, and enrich bronze into the silver beneficiary table.

    Adds: birth_date/death_date (typed-date aliases), age_2008, age_band,
    is_deceased, state_abbr/state_name, the 11 decoded chronic-condition
    booleans, and chronic_condition_count. See
    docs/IMPLEMENTATION_SPEC.md §7.2, §8, §14.
    """
    df = bronze_df.dropDuplicates(["DESYNPUF_ID"])

    df = df.withColumn("birth_date", F.col("BENE_BIRTH_DT")).withColumn("death_date", F.col("BENE_DEATH_DT"))

    df = df.withColumn(
        "age_2008", F.floor(F.months_between(F.lit(REFERENCE_DATE), F.col("birth_date")) / F.lit(12)).cast("int")
    )
    df = df.withColumn(
        "age_band",
        F.when(F.col("age_2008") < 65, "Under 65")
        .when(F.col("age_2008") < 75, "65-74")
        .when(F.col("age_2008") < 85, "75-84")
        .otherwise("85+"),
    )

    df = df.withColumn("is_deceased", F.col("death_date").isNotNull())

    df = df.withColumn("state_abbr", _state_lookup_column(F.col("SP_STATE_CODE"), 0))
    df = df.withColumn("state_name", _state_lookup_column(F.col("SP_STATE_CODE"), 1))

    for raw_col, silver_col in CHRONIC_CONDITION_COLUMNS.items():
        df = df.withColumn(silver_col, F.col(raw_col) == F.lit("1"))

    condition_count_expr = sum(F.col(c).cast("int") for c in CHRONIC_CONDITION_COLUMNS.values())
    df = df.withColumn("chronic_condition_count", condition_count_expr)

    return df
