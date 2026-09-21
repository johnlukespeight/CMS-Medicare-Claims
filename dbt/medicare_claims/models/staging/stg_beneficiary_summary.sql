-- Renamed to snake_case, typed, chronic-condition flags decoded to
-- booleans. 1:1 grain with source. See docs/IMPLEMENTATION_SPEC.md §7.3, §8.
--
-- CMS encodes SP_* as 1=Yes/2=No (confirmed against the real file, see
-- notebooks/00_data_profiling.ipynb §4) -- decoded here and nowhere else
-- in this dbt project.

with source as (
    select * from {{ source('medicare_raw', 'beneficiary_summary') }}
),

renamed as (
    select
        DESYNPUF_ID as desynpuf_id,

        -- BigQuery autodetected these as INTEGER (e.g. 19430501); PARSE_DATE
        -- needs a string. NULL BENE_DEATH_DT (alive as of the file's
        -- reference date) stays NULL -- not imputed, see spec §8.
        parse_date('%Y%m%d', cast(BENE_BIRTH_DT as string)) as birth_date,
        parse_date('%Y%m%d', cast(BENE_DEATH_DT as string)) as death_date,

        BENE_SEX_IDENT_CD as sex_cd,
        BENE_RACE_CD as race_cd,
        BENE_ESRD_IND as esrd_ind,

        -- Zero-padded back to the 2-digit SSA code the seed table keys on
        -- (BigQuery's autodetect stored this as INTEGER, dropping the
        -- leading zero on codes 01-09).
        lpad(cast(SP_STATE_CODE as string), 2, '0') as state_code,
        BENE_COUNTY_CD as county_cd,

        BENE_HI_CVRAGE_TOT_MONS as hi_coverage_months,
        BENE_SMI_CVRAGE_TOT_MONS as smi_coverage_months,
        BENE_HMO_CVRAGE_TOT_MONS as hmo_coverage_months,
        PLAN_CVRG_MOS_NUM as plan_coverage_months,

        (SP_ALZHDMTA = 1) as has_alzheimers,
        (SP_CHF = 1) as has_chf,
        (SP_CHRNKIDN = 1) as has_chronic_kidney_disease,
        (SP_CNCR = 1) as has_cancer,
        (SP_COPD = 1) as has_copd,
        (SP_DEPRESSN = 1) as has_depression,
        (SP_DIABETES = 1) as has_diabetes,
        (SP_ISCHMCHT = 1) as has_ischemic_heart_disease,
        (SP_OSTEOPRS = 1) as has_osteoporosis,
        (SP_RA_OA = 1) as has_rheumatoid_or_osteoarthritis,
        (SP_STRKETIA = 1) as has_stroke_or_tia,

        -- Not guaranteed non-negative (claim adjustments) -- preserved
        -- as-is, never clipped. See spec §8.
        MEDREIMB_IP as medreimb_ip,
        BENRES_IP as benres_ip,
        PPPYMT_IP as pppymt_ip,
        MEDREIMB_OP as medreimb_op,
        BENRES_OP as benres_op,
        PPPYMT_OP as pppymt_op,
        MEDREIMB_CAR as medreimb_car,
        BENRES_CAR as benres_car,
        PPPYMT_CAR as pppymt_car
    from source
)

select * from renamed
