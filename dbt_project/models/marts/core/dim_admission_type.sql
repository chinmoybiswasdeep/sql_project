-- Grain: one row per source admission_type.
select
    admission_type,
    admission_group,
    is_planned,
    is_observation,
    description
from {{ ref('admission_type_groups') }}
