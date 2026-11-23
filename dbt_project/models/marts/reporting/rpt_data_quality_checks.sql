with last_run as (
    select max(run_id) as run_id from {{ source('pipeline_meta', 'validation_results') }}
)
select v.check_name, v.table_name, v.severity, v.status, v.flagged_rows, v.description,
       v.checked_at, v.run_id
from {{ source('pipeline_meta', 'validation_results') }} v
inner join last_run lr on lr.run_id = v.run_id
