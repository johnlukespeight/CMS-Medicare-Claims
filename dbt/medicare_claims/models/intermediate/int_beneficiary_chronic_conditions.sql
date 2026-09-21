-- One row per beneficiary x condition (11 rows per beneficiary), for
-- prevalence analysis in mart_chronic_condition_prevalence.
-- See docs/IMPLEMENTATION_SPEC.md §7.3.

with unpivoted as (
    select
        desynpuf_id,
        state_code,
        condition,
        has_condition
    from {{ ref('stg_beneficiary_summary') }}
    unpivot (
        has_condition for condition in (
            has_alzheimers as 'alzheimers',
            has_chf as 'chf',
            has_chronic_kidney_disease as 'chronic_kidney_disease',
            has_cancer as 'cancer',
            has_copd as 'copd',
            has_depression as 'depression',
            has_diabetes as 'diabetes',
            has_ischemic_heart_disease as 'ischemic_heart_disease',
            has_osteoporosis as 'osteoporosis',
            has_rheumatoid_or_osteoarthritis as 'rheumatoid_or_osteoarthritis',
            has_stroke_or_tia as 'stroke_or_tia'
        )
    )
)

select * from unpivoted
