from datetime import date

from pyspark.sql import Row
from transforms.beneficiary_transforms import (
    CHRONIC_CONDITION_COLUMNS,
    RAW_SCHEMA,
    to_bronze,
    to_silver,
)

from tests.conftest import SAMPLE_CSV_PATH

DEFAULT_ROW = {
    "DESYNPUF_ID": "SYN0000001",
    "BENE_BIRTH_DT": "19400315",
    "BENE_DEATH_DT": None,
    "BENE_SEX_IDENT_CD": "1",
    "BENE_RACE_CD": "1",
    "BENE_ESRD_IND": "0",
    "SP_STATE_CODE": "05",
    "BENE_COUNTY_CD": "100",
    "BENE_HI_CVRAGE_TOT_MONS": "12",
    "BENE_SMI_CVRAGE_TOT_MONS": "12",
    "BENE_HMO_CVRAGE_TOT_MONS": "0",
    "PLAN_CVRG_MOS_NUM": "12",
    **{col: "2" for col in CHRONIC_CONDITION_COLUMNS},  # no conditions by default
    "MEDREIMB_IP": "0.00",
    "BENRES_IP": "0.00",
    "PPPYMT_IP": "0.00",
    "MEDREIMB_OP": "0.00",
    "BENRES_OP": "0.00",
    "PPPYMT_OP": "0.00",
    "MEDREIMB_CAR": "0.00",
    "BENRES_CAR": "0.00",
    "PPPYMT_CAR": "0.00",
}


def make_row(**overrides) -> Row:
    return Row(**{**DEFAULT_ROW, **overrides})


def make_silver(spark, rows):
    df = spark.createDataFrame(rows, schema=RAW_SCHEMA)
    return to_silver(to_bronze(df))


def test_bronze_casts_types(spark):
    df = spark.createDataFrame([make_row()], schema=RAW_SCHEMA)
    bronze = to_bronze(df)
    row = bronze.collect()[0]
    assert row["BENE_BIRTH_DT"] == date(1940, 3, 15)
    assert row["BENE_DEATH_DT"] is None
    assert row["PLAN_CVRG_MOS_NUM"] == 12
    assert isinstance(row["MEDREIMB_IP"], float)
    assert row["_ingested_at"] is not None


def test_silver_computes_age_and_age_band(spark):
    # Born 1940-03-15: turns 68 by 2008-12-31 -> "65-74" band.
    silver = make_silver(spark, [make_row(BENE_BIRTH_DT="19400315")])
    row = silver.collect()[0]
    assert row["age_2008"] == 68
    assert row["age_band"] == "65-74"


def test_silver_age_band_boundaries(spark):
    rows = [
        make_row(DESYNPUF_ID="A", BENE_BIRTH_DT="19601231"),  # turns 48 -> Under 65
        make_row(DESYNPUF_ID="B", BENE_BIRTH_DT="19431231"),  # turns 65 -> 65-74
        make_row(DESYNPUF_ID="C", BENE_BIRTH_DT="19331231"),  # turns 75 -> 75-84
        make_row(DESYNPUF_ID="D", BENE_BIRTH_DT="19201231"),  # turns 88 -> 85+
    ]
    silver = make_silver(spark, rows).select("DESYNPUF_ID", "age_2008", "age_band")
    result = {r["DESYNPUF_ID"]: (r["age_2008"], r["age_band"]) for r in silver.collect()}
    assert result["A"] == (48, "Under 65")
    assert result["B"] == (65, "65-74")
    assert result["C"] == (75, "75-84")
    assert result["D"] == (88, "85+")


def test_silver_is_deceased_reflects_death_date(spark):
    rows = [
        make_row(DESYNPUF_ID="ALIVE", BENE_DEATH_DT=None),
        make_row(DESYNPUF_ID="DECEASED", BENE_DEATH_DT="20080615"),
    ]
    silver = make_silver(spark, rows).select("DESYNPUF_ID", "is_deceased")
    result = {r["DESYNPUF_ID"]: r["is_deceased"] for r in silver.collect()}
    assert result["ALIVE"] is False
    assert result["DECEASED"] is True


def test_silver_decodes_chronic_condition_flags(spark):
    row = make_row(SP_DIABETES="1", SP_CHF="1", SP_CNCR="2")
    silver = make_silver(spark, [row]).collect()[0]
    assert silver["has_diabetes"] is True
    assert silver["has_chf"] is True
    assert silver["has_cancer"] is False
    assert silver["chronic_condition_count"] == 2


def test_silver_chronic_condition_count_matches_flag_sum(spark):
    row = make_row(SP_DIABETES="1", SP_CHF="1", SP_CNCR="1", SP_COPD="1")
    silver = make_silver(spark, [row]).collect()[0]
    assert silver["chronic_condition_count"] == 4


def test_silver_state_lookup(spark):
    # 05/54 verified against the official CMS DE-SynPUF codebook (BEN-7) —
    # 54 is CMS's own "Other/Territory" catch-all, not a real US state.
    rows = [
        make_row(DESYNPUF_ID="CA_BENE", SP_STATE_CODE="05"),
        make_row(DESYNPUF_ID="OTHER_BENE", SP_STATE_CODE="54"),
    ]
    silver = make_silver(spark, rows).select("DESYNPUF_ID", "state_abbr", "state_name")
    result = {r["DESYNPUF_ID"]: (r["state_abbr"], r["state_name"]) for r in silver.collect()}
    assert result["CA_BENE"] == ("CA", "California")
    assert result["OTHER_BENE"] == ("OTHER", "Other/Territory")


def test_silver_preserves_negative_reimbursement_values(spark):
    # Confirmed against the real file (notebooks/00_data_profiling.ipynb §6):
    # negative MEDREIMB_IP/OP values are real claim adjustments, never clipped.
    row = make_row(MEDREIMB_IP="-3000.00")
    silver = make_silver(spark, [row]).collect()[0]
    assert silver["MEDREIMB_IP"] == -3000.00


def test_silver_dedupes_on_beneficiary_id(spark):
    rows = [make_row(DESYNPUF_ID="DUPLICATE"), make_row(DESYNPUF_ID="DUPLICATE")]
    silver = make_silver(spark, rows)
    assert silver.filter(silver["DESYNPUF_ID"] == "DUPLICATE").count() == 1


def test_silver_matches_hand_checked_row_from_the_real_fixture(spark):
    """Runs the real pipeline against data/samples/beneficiary_summary_sample.csv
    and checks one specific, hand-verified beneficiary (DESYNPUF_ID
    D783188324D155DD): born 1911-08-01 (age 97 as of 2008-12-31, "85+"),
    alive, SP_STATE_CODE=25 (Mississippi), with SP_ALZHDMTA/SP_CHF/SP_COPD/
    SP_DEPRESSN/SP_DIABETES/SP_ISCHMCHT=1 (6 conditions) and
    MEDREIMB_IP=5060.00 — values read directly off the raw CSV row by hand.
    """
    raw_df = spark.read.csv(str(SAMPLE_CSV_PATH), header=True, schema=RAW_SCHEMA)
    silver = to_silver(to_bronze(raw_df))

    row = silver.filter(silver["DESYNPUF_ID"] == "D783188324D155DD").collect()[0]

    assert row["age_2008"] == 97
    assert row["age_band"] == "85+"
    assert row["is_deceased"] is False
    assert row["state_abbr"] == "MS"
    assert row["state_name"] == "Mississippi"
    assert row["has_alzheimers"] is True
    assert row["has_chf"] is True
    assert row["has_copd"] is True
    assert row["has_depression"] is True
    assert row["has_diabetes"] is True
    assert row["has_ischemic_heart_disease"] is True
    assert row["has_cancer"] is False
    assert row["chronic_condition_count"] == 6
    assert row["MEDREIMB_IP"] == 5060.00
    assert row["MEDREIMB_OP"] == 730.00
    assert row["MEDREIMB_CAR"] == 2820.00


def test_silver_row_count_matches_deduped_fixture(spark):
    raw_df = spark.read.csv(str(SAMPLE_CSV_PATH), header=True, schema=RAW_SCHEMA)
    silver = to_silver(to_bronze(raw_df))
    assert silver.count() == raw_df.dropDuplicates(["DESYNPUF_ID"]).count()
