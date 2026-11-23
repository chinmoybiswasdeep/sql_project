-- Grain: one row per normalised drug name (medication_key).
-- MIMIC drug names are free text; normalisation collapses case and spacing
-- only. Different brand/generic names for the same agent remain separate
-- (no RxNorm mapping in the demo scope).
with orders as (
    select drug_name_normalized, drug_type, route
    from {{ ref('stg_prescriptions') }}
),

ranked_route as (
    select
        drug_name_normalized,
        route,
        row_number() over (
            partition by drug_name_normalized order by count(*) desc, route
        ) as rn
    from orders
    group by drug_name_normalized, route
)

select
    md5(o.drug_name_normalized)                    as medication_key,
    o.drug_name_normalized                         as drug_name,
    count(*)                                       as n_orders,
    max(r.route)                                   as most_common_route
from orders o
left join ranked_route r
    on r.drug_name_normalized = o.drug_name_normalized and r.rn = 1
group by o.drug_name_normalized
