-- Grain: one row per laboratory measurement (labevent_id).
--
-- Incremental: on the full dataset labevents exceeds 150M rows, so rebuilds
-- only process measurements charted on/after the latest loaded charttime
-- (minus a 1-day safety margin) and upsert on labevent_id (delete+insert).
-- MIMIC releases are static; the pattern exists for append-style refreshes
-- and so the model scales. A full rebuild is `dbt run --full-refresh`.
{{ config(
    materialized='incremental',
    unique_key='labevent_id',
    incremental_strategy='delete+insert',
    indexes=[
        {'columns': ['labevent_id'], 'unique': true},
        {'columns': ['hadm_id']},
        {'columns': ['itemid']},
    ]
) }}

select
    l.labevent_id,
    l.subject_id,
    l.hadm_id,
    l.itemid,
    l.charttime,
    l.value_numeric,
    l.value_unit,
    l.ref_range_lower,
    l.ref_range_upper,
    l.flag_abnormal,
    l.range_direction,
    l.priority,
    l.hadm_id is not null                          as is_admission_linked
from {{ ref('stg_labevents') }} l
{% if is_incremental() %}
where l.charttime >= (select max(charttime) - interval '1 day' from {{ this }})
{% endif %}
