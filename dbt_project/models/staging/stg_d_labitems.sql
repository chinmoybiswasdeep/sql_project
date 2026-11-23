select
    itemid,
    coalesce(label, '(unlabelled item ' || itemid || ')') as lab_test_name,
    fluid,
    category                                      as lab_category
from {{ source('mimic_raw', 'd_labitems') }}
