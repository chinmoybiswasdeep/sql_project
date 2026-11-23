-- Grain: one row per care unit name. Union of the reference seed and every
-- unit observed in transfers/ICU stays, so new units in the full dataset
-- appear as 'Unclassified' instead of silently disappearing.
with observed as (
    select care_unit as careunit from {{ ref('stg_transfers') }} where care_unit is not null
    union
    select first_careunit from {{ ref('stg_icustays') }}
    union
    select last_careunit from {{ ref('stg_icustays') }}
),

all_units as (
    select careunit from observed
    union
    select careunit from {{ ref('care_unit_types') }}
)

select
    u.careunit                                     as care_unit,
    coalesce(s.unit_type, 'Unclassified')          as unit_type,
    coalesce(s.is_icu, false)                      as is_icu,
    u.careunit in (select careunit from observed)  as is_observed_in_data
from all_units u
left join {{ ref('care_unit_types') }} s on s.careunit = u.careunit
