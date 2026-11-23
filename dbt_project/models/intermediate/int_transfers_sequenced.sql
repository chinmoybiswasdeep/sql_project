-- Grain: one row per patient movement into a care unit (transfer_id) that is
-- linked to a hospital admission.
--
-- * 'discharge' events are dropped: they carry no care unit and mark the end
--   of the stay, not a movement into a unit.
-- * ED visits with no hadm_id (ED encounters that did not become an
--   admission) are excluded from this admission-centred model.
-- * is_unit_change: the care unit differs from the previous movement's unit
--   (bed moves inside the same unit are not counted as unit changes).
with transfers as (
    select *
    from {{ ref('stg_transfers') }}
    where event_type <> 'discharge'
      and hadm_id is not null
),

unit_types as (
    select * from {{ ref('care_unit_types') }}
),

sequenced as (
    select
        t.transfer_id,
        t.hadm_id,
        t.subject_id,
        t.event_type,
        t.care_unit,
        coalesce(ut.unit_type, 'Unclassified')     as unit_type,
        coalesce(ut.is_icu, false)                 as is_icu_unit,
        t.intime,
        t.outtime,
        t.unit_hours,
        row_number() over w                        as movement_seq,
        lag(t.care_unit) over w                    as prev_care_unit,
        lag(coalesce(ut.unit_type, 'Unclassified')) over w as prev_unit_type
    from transfers t
    left join unit_types ut on ut.careunit = t.care_unit
    window w as (partition by t.hadm_id order by t.intime, t.transfer_id)
)

select
    sequenced.*,
    coalesce(prev_care_unit is not null and prev_care_unit <> care_unit, false) as is_unit_change
from sequenced
