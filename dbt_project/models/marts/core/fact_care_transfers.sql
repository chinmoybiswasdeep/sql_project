-- Grain: one row per movement into a care unit (transfer_id) linked to an
-- admission. Discharge events and ED-only visits are excluded upstream.
select
    transfer_id,
    hadm_id,
    subject_id,
    event_type,
    care_unit,
    unit_type,
    is_icu_unit,
    movement_seq,
    prev_care_unit,
    prev_unit_type,
    is_unit_change,
    intime,
    outtime,
    unit_hours
from {{ ref('int_transfers_sequenced') }}
