-- =============================================================================
-- Query 14: Frequency and duration of ICU care-unit transfers
-- Module: C. ICU analytics
-- Business question: How do patients flow into, out of and between ICUs, and how long do they stay in the unit they leave?
-- Metric: Unit-type transitions that involve an ICU (ward to ICU, ICU to ward, ICU to ICU, ED to ICU, ...): count, share, distinct admissions, and median hours in the origin unit before the move.
-- Output grain: One row per (from_unit_type, to_unit_type) transition involving an ICU.
-- Joins: fact_care_transfers with LAG over movements within each hadm_id to recover the origin unit and its duration.
-- Denominator and exclusions: Unit changes only (is_unit_change); bed moves within the same unit are excluded. Admission-linked movements only.
-- Potential biases: Unit types come from a reference seed; Unclassified units would be pooled. Short origin durations can reflect documentation timing. 'Discharge lounge -> ICU' is NOT a reversed discharge: in this data 25 of 26 admissions whose first unit is the Discharge Lounge are elective/same-day surgical admissions, so the lounge works as pre-procedure holding and the move is a planned post-operative ICU admission.
-- Expected output: from_unit_type, to_unit_type, transitions, pct_of_icu_transitions, admissions, median_hours_in_origin_unit.
-- Techniques: LAG window function, CTE, FILTER, window share, percentile_cont.
-- =============================================================================
with moves as (
    select
        hadm_id,
        prev_unit_type                                                     as from_unit_type,
        unit_type                                                          as to_unit_type,
        lag(is_icu_unit) over w                                            as from_is_icu,
        is_icu_unit                                                        as to_is_icu,
        lag(unit_hours) over w                                             as hours_in_origin_unit,
        is_unit_change
    from marts.fact_care_transfers
    window w as (partition by hadm_id order by movement_seq)
)
select
    from_unit_type,
    to_unit_type,
    count(*)                                                               as transitions,
    round(100.0 * count(*) / sum(count(*)) over (), 1)                     as pct_of_icu_transitions,
    count(distinct hadm_id)                                                as admissions,
    round(percentile_cont(0.5) within group (order by hours_in_origin_unit)::numeric, 1)
                                                                           as median_hours_in_origin_unit
from moves
where is_unit_change
  and (from_is_icu or to_is_icu)
group by from_unit_type, to_unit_type
order by transitions desc;
