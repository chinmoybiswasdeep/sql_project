-- =============================================================================
-- Query 19: Medication prescribing patterns
-- Module: D. Clinical analytics
-- Business question: Which medications are ordered most, how widely across admissions, by which route, and for how long?
-- Metric: Per normalised drug name: orders, admissions with an order, % of admissions, orders per exposed admission, most common route, median order duration (hours). Top 20 by admissions exposed.
-- Output grain: One row per drug (top 20).
-- Joins: fact_medication_orders aggregated by drug; modal route from dim_medication (one row per drug, so no fan-out).
-- Denominator and exclusions: Therapeutic orders only: drug_type = 'BASE' (diluents and IV base solutions such as '0.9% sodium chloride' and 'bag', 20% of orders) and line flushes are excluded because they are carriers, not therapies. % of admissions uses all admissions. Order durations with stop before start are left out of the duration median (flagged has_inverted_times).
-- Potential biases: Orders are not administrations (use emar for administration). Free-text drug names: brand and generic names, and different strengths, are not merged (no RxNorm mapping). PRN protocol orders (for example dextrose 50%, glucagon for hypoglycaemia) count as exposure even if never given.
-- Expected output: exposure_rank, drug_name, orders, admissions_exposed, pct_admissions_exposed, orders_per_exposed_admission, most_common_route, median_order_hours.
-- Techniques: CTE aggregation, DENSE_RANK, percentile_cont with FILTER, join to dimension.
-- =============================================================================
with by_drug as (
    select
        medication_key,
        drug_name_normalized                                         as drug_name,
        count(*)                                                     as orders,
        count(distinct hadm_id)                                      as admissions_exposed,
        percentile_cont(0.5) within group (order by order_duration_hours)
            filter (where not has_inverted_times)                    as median_order_hours
    from marts.fact_medication_orders
    where drug_type <> 'BASE'
      and drug_name_normalized not like '%flush%'
    group by medication_key, drug_name_normalized
)
select
    dense_rank() over (order by b.admissions_exposed desc)           as exposure_rank,
    b.drug_name,
    b.orders,
    b.admissions_exposed,
    round(100.0 * b.admissions_exposed / (select count(*) from marts.fact_admissions), 1)
                                                                     as pct_admissions_exposed,
    round(b.orders::numeric / b.admissions_exposed, 2)               as orders_per_exposed_admission,
    m.most_common_route,
    round(b.median_order_hours::numeric, 1)                          as median_order_hours
from by_drug b
join marts.dim_medication m on m.medication_key = b.medication_key
order by b.admissions_exposed desc, b.orders desc
limit 20;
