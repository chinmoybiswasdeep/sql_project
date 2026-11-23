with latest as (
    select
        l.*,
        row_number() over (partition by l.table_name order by l.logged_at desc) as rn
    from {{ source('pipeline_meta', 'ingestion_table_log') }} l
),
last_load as (
    select table_name, max(logged_at) as last_successful_load_at
    from {{ source('pipeline_meta', 'ingestion_table_log') }}
    where status = 'loaded'
    group by table_name
)
select
    latest.table_name,
    latest.status                                  as latest_status,
    latest.run_id                                  as latest_run_id,
    latest.source_rows,
    latest.loaded_rows,
    latest.rejected_rows,
    latest.duplicate_key_rows,
    latest.duration_seconds,
    ll.last_successful_load_at
from latest
left join last_load ll on ll.table_name = latest.table_name
where latest.rn = 1
