-- One row per beneficiary: demographics, state, age band, deceased flag,
-- chronic condition count. See docs/IMPLEMENTATION_SPEC.md §7.3.

with beneficiary as (
    select * from {{ ref('stg_beneficiary_summary') }}
),

with_state as (
    select
        beneficiary.*,
        ssa.state_abbr,
        ssa.state_name
    from beneficiary
    left join {{ ref('ssa_state_codes') }} as ssa
        on beneficiary.state_code = ssa.state_code
),

with_age as (
    select
        *,
        -- Age as of the file's reference date, 2008-12-31 (spec §14).
        -- DATE_DIFF(..., YEAR) already accounts for whether the birthday
        -- has occurred -- verified empirically, not assumed.
        date_diff(date '2008-12-31', birth_date, year) as age_2008
    from with_state
),

final as (
    select
        desynpuf_id,
        birth_date,
        death_date,
        (death_date is not null) as is_deceased,
        sex_cd,
        race_cd,
        esrd_ind,
        state_code,
        state_abbr,
        state_name,
        age_2008,
        case
            when age_2008 < 65 then 'Under 65'
            when age_2008 < 75 then '65-74'
            when age_2008 < 85 then '75-84'
            else '85+'
        end as age_band,
        (
            cast(has_alzheimers as int64) + cast(has_chf as int64)
            + cast(has_chronic_kidney_disease as int64) + cast(has_cancer as int64)
            + cast(has_copd as int64) + cast(has_depression as int64)
            + cast(has_diabetes as int64) + cast(has_ischemic_heart_disease as int64)
            + cast(has_osteoporosis as int64) + cast(has_rheumatoid_or_osteoarthritis as int64)
            + cast(has_stroke_or_tia as int64)
        ) as chronic_condition_count
    from with_age
)

select * from final
