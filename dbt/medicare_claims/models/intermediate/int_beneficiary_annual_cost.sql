-- One row per beneficiary. total_cost_2008 = Medicare-paid IP+OP+CAR only
-- (MEDREIMB_*) -- never silently combined with beneficiary-paid amounts
-- (BENRES_*), which are tracked as a separate total. See spec §14.

select
    desynpuf_id,

    medreimb_ip,
    medreimb_op,
    medreimb_car,
    medreimb_ip + medreimb_op + medreimb_car as total_cost_2008,

    benres_ip,
    benres_op,
    benres_car,
    benres_ip + benres_op + benres_car as total_beneficiary_responsibility_2008
from {{ ref('stg_beneficiary_summary') }}
