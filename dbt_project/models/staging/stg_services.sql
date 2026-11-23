select
    hadm_id,
    subject_id,
    transfertime                                  as service_start_time,
    prev_service,
    curr_service
from {{ source('mimic_raw', 'services') }}
