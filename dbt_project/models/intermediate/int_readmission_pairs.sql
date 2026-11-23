-- Grain: one row per hospital admission, viewed as a potential *index*
-- discharge for 30-day readmission measurement.
--
-- Method (see docs/metric_definitions.md#30-day-readmission):
--   * Pair each admission with the same patient's NEXT admission
--     (LEAD over admittime). Only the next admission matters: if it falls
--     outside the window, every later one does too.
--   * Index eligibility (denominator) excludes, in priority order:
--       missing_dischtime            LOS/window cannot be computed
--       died_in_hospital             no opportunity for readmission
--       transfer_to_acute_care       episode continues at another hospital
--       left_against_medical_advice  follows CMS hospital-wide measure practice
--       overlapping_next_admission   next admission starts before this discharge
--                                    (data anomaly; not a readmission)
--   * Numerator: eligible index whose next admission starts within
--     [dischtime, dischtime + window]. Returns within 24h are counted and flagged (is_readmitted_within_24h).
--   * "Unplanned" = next admission type not ELECTIVE / SURGICAL SAME DAY.
--     This is NOT a "preventable" label; no validated preventability
--     algorithm is applied.
--   * Limitation: only returns to this hospital are observed, and there is no
--     per-patient end-of-follow-up date, so late index discharges may be
--     under-counted (right censoring). See docs/limitations.md.

with admissions as (
    select * from {{ ref('int_admissions_enriched') }}
),

sequenced as (
    select
        hadm_id,
        subject_id,
        admittime,
        dischtime,
        discharge_location,
        died_in_hospital,
        admission_type,
        is_planned,
        is_observation,
        lead(hadm_id) over w                       as next_hadm_id,
        lead(admittime) over w                     as next_admittime,
        lead(admission_type) over w                as next_admission_type,
        lead(is_planned) over w                    as next_is_planned,
        lead(is_observation) over w                as next_is_observation
    from admissions
    window w as (partition by subject_id order by admittime, hadm_id)
),

classified as (
    select
        sequenced.*,
        case
            when next_admittime is not null and dischtime is not null
            then {{ days_between('dischtime', 'next_admittime') }}
        end                                        as days_to_next_admission,
        case
            when dischtime is null then 'missing_dischtime'
            when died_in_hospital or discharge_location = 'DIED' then 'died_in_hospital'
            when discharge_location = 'ACUTE HOSPITAL' then 'transfer_to_acute_care'
            when discharge_location = 'AGAINST ADVICE' then 'left_against_medical_advice'
            when next_admittime < dischtime then 'overlapping_next_admission'
        end                                        as exclusion_reason
    from sequenced
)

select
    hadm_id                                        as index_hadm_id,
    subject_id,
    admittime                                      as index_admittime,
    dischtime                                      as index_dischtime,
    admission_type                                 as index_admission_type,
    is_observation                                 as index_is_observation,
    discharge_location,
    next_hadm_id,
    next_admittime,
    next_admission_type,
    next_is_planned,
    next_is_observation,
    days_to_next_admission,
    exclusion_reason,
    exclusion_reason is null                       as is_eligible_index,
    next_hadm_id is null                           as is_last_observed_admission,
    coalesce(exclusion_reason is null
        and next_admittime >= dischtime
        and next_admittime <= {{ add_hours('dischtime', readmission_window_hours()) }}, false)
                                                   as is_readmitted_30d,
    coalesce(exclusion_reason is null
        and next_admittime >= dischtime
        and next_admittime <= {{ add_hours('dischtime', readmission_window_hours()) }}
        and not next_is_planned, false)            as is_unplanned_readmitted_30d,
    coalesce(exclusion_reason is null
        and next_admittime >= dischtime
        and next_admittime < {{ add_hours('dischtime', 24) }}, false)
                                                   as is_readmitted_within_24h
from classified
