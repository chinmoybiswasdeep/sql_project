select
    subject_id,
    gender                         as sex,
    anchor_age,
    anchor_year,
    anchor_year_group,
    dod                            as date_of_death,
    anchor_age >= 89               as is_age_top_coded
from {{ source('mimic_raw', 'patients') }}
