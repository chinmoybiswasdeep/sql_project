-- Grain: one row per laboratory item (itemid).
select
    itemid,
    lab_test_name,
    fluid,
    lab_category
from {{ ref('stg_d_labitems') }}
