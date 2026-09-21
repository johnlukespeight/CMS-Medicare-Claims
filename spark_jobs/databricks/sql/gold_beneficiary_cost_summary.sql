-- docs/IMPLEMENTATION_SPEC.md §7.2 gold.beneficiary_cost_summary
-- Grain: one row per beneficiary. MEDREIMB_* (Medicare-paid) and BENRES_*
-- (beneficiary-paid) are kept as separate totals per §14 — never silently
-- combined into one misleading "total cost".
CREATE OR REPLACE TABLE medicare.gold.beneficiary_cost_summary AS
SELECT
    DESYNPUF_ID AS desynpuf_id,
    state_abbr,
    state_name,
    age_band,
    chronic_condition_count,
    is_deceased,
    MEDREIMB_IP AS medreimb_ip,
    MEDREIMB_OP AS medreimb_op,
    MEDREIMB_CAR AS medreimb_car,
    MEDREIMB_IP + MEDREIMB_OP + MEDREIMB_CAR AS total_medicare_reimbursement,
    BENRES_IP AS benres_ip,
    BENRES_OP AS benres_op,
    BENRES_CAR AS benres_car,
    BENRES_IP + BENRES_OP + BENRES_CAR AS total_beneficiary_responsibility
FROM medicare.silver.beneficiary;
