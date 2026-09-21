-- docs/IMPLEMENTATION_SPEC.md §7.2 gold.chronic_condition_prevalence
-- Grain: one row per condition x state. UNPIVOTs the 11 has_* boolean
-- columns from silver.beneficiary so prevalence can be computed generically
-- instead of copy-pasting one aggregate per condition.
CREATE OR REPLACE TABLE medicare.gold.chronic_condition_prevalence AS
WITH unpivoted AS (
    SELECT
        state_abbr,
        state_name,
        MEDREIMB_IP + MEDREIMB_OP + MEDREIMB_CAR AS total_medicare_reimbursement,
        condition,
        has_condition
    FROM medicare.silver.beneficiary
    UNPIVOT (
        has_condition FOR condition IN (
            has_alzheimers AS alzheimers,
            has_chf AS chf,
            has_chronic_kidney_disease AS chronic_kidney_disease,
            has_cancer AS cancer,
            has_copd AS copd,
            has_depression AS depression,
            has_diabetes AS diabetes,
            has_ischemic_heart_disease AS ischemic_heart_disease,
            has_osteoporosis AS osteoporosis,
            has_rheumatoid_or_osteoarthritis AS rheumatoid_or_osteoarthritis,
            has_stroke_or_tia AS stroke_or_tia
        )
    )
)
SELECT
    condition,
    state_abbr,
    state_name,
    COUNT(*) AS total_beneficiaries_in_state,
    SUM(CAST(has_condition AS INT)) AS beneficiaries_with_condition,
    ROUND(SUM(CAST(has_condition AS INT)) / COUNT(*), 4) AS prevalence_rate,
    ROUND(AVG(CASE WHEN has_condition THEN total_medicare_reimbursement END), 2) AS avg_total_cost_with_condition
FROM unpivoted
GROUP BY condition, state_abbr, state_name
ORDER BY condition, state_abbr;
