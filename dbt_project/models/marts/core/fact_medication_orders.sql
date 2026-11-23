-- Grain: one prescription order (prescription_key = hash of
-- hadm_id, pharmacy_id, drug, starttime). Orders are not administrations.
select
    rx.prescription_key,
    rx.hadm_id,
    rx.subject_id,
    md5(rx.drug_name_normalized)                   as medication_key,
    rx.drug_name_normalized,
    rx.drug_type,
    rx.route,
    rx.starttime,
    rx.stoptime,
    rx.order_duration_hours,
    rx.has_inverted_times
from {{ ref('stg_prescriptions') }} rx
