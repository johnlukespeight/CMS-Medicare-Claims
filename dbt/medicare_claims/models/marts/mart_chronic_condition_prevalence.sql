-- Prevalence and average cost per condition, both by state and overall
-- (state_abbr is NULL, state_name = 'All States' on the overall rows).
-- See docs/IMPLEMENTATION_SPEC.md §7.3.

with conditions as (
    select
        c.desynpuf_id,
        c.condition,
        c.has_condition,
        b.state_abbr,
        b.state_name,
        cost.total_cost_2008
    from {{ ref('int_beneficiary_chronic_conditions') }} as c
    left join {{ ref('dim_beneficiary') }} as b on c.desynpuf_id = b.desynpuf_id
    left join {{ ref('int_beneficiary_annual_cost') }} as cost on c.desynpuf_id = cost.desynpuf_id
),

by_state as (
    select
        condition,
        state_abbr,
        state_name,
        count(*) as total_beneficiaries_in_state,
        sum(cast(has_condition as int64)) as beneficiaries_with_condition,
        round(sum(cast(has_condition as int64)) / count(*), 4) as prevalence_rate,
        round(avg(case when has_condition then total_cost_2008 end), 2) as avg_total_cost_with_condition
    from conditions
    group by condition, state_abbr, state_name
),

overall as (
    select
        condition,
        cast(null as string) as state_abbr,
        'All States' as state_name,
        count(*) as total_beneficiaries_in_state,
        sum(cast(has_condition as int64)) as beneficiaries_with_condition,
        round(sum(cast(has_condition as int64)) / count(*), 4) as prevalence_rate,
        round(avg(case when has_condition then total_cost_2008 end), 2) as avg_total_cost_with_condition
    from conditions
    group by condition
)

select * from by_state
union all
select * from overall
