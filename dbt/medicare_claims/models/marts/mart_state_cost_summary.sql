-- Enrollment and total/average cost by state. See spec §7.3.

select
    b.state_code,
    b.state_abbr,
    b.state_name,
    count(*) as beneficiary_count,
    sum(cost.total_cost_2008) as total_medicare_reimbursement,
    round(avg(cost.total_cost_2008), 2) as avg_medicare_reimbursement_per_beneficiary
from {{ ref('dim_beneficiary') }} as b
left join {{ ref('int_beneficiary_annual_cost') }} as cost on b.desynpuf_id = cost.desynpuf_id
group by b.state_code, b.state_abbr, b.state_name
order by beneficiary_count desc
