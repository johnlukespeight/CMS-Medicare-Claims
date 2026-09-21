-- Grain: one row per beneficiary per year (2008 only for now -- see spec
-- §35 for the deferred multi-year extension). Foreign key to
-- dim_beneficiary via desynpuf_id.

select
    desynpuf_id,
    2008 as year,
    medreimb_ip,
    medreimb_op,
    medreimb_car,
    total_cost_2008 as total_medicare_reimbursement,
    benres_ip,
    benres_op,
    benres_car,
    total_beneficiary_responsibility_2008 as total_beneficiary_responsibility
from {{ ref('int_beneficiary_annual_cost') }}
