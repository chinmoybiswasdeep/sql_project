select table_name, column_name, row_count, null_count, null_pct, sampled, run_id
from (
    select p.*,
           row_number() over (partition by table_name, column_name order by run_id desc) as rn
    from {{ source('pipeline_meta', 'column_profile') }} p
) latest
where rn = 1
