# Optional BigQuery Backend (not validated)

Credentialed PhysioNet users can link their account to Google Cloud and query MIMIC-IV in
BigQuery (`physionet-data.mimiciv_3_1_hosp`, `physionet-data.mimiciv_3_1_icu`). That lets
the full dataset be analysed without downloading it.

## What exists

- A `bigquery` target in [`dbt_project/profiles.yml`](../dbt_project/profiles.yml) (OAuth).
- Adapter-dispatched macros for the date arithmetic used in the models
  (`hours_between`, `add_hours`) with `bigquery__` implementations.
- The optional dependency group: `pip install -e ".[bigquery]"`.

## What would still need to change

1. Point the `mimic_raw` source at the PhysioNet project, e.g. with a
   `vars: {raw_database: physionet-data, raw_schema: mimiciv_3_1_hosp}` override. The ICU
   tables live in a separate dataset, so a second source is needed.
2. Port a few PostgreSQL-specific expressions in staging and marts: `md5()` (BigQuery
   returns BYTES, so wrap it in `to_hex`), `regexp_replace(..., 'g')`, `percentile_cont ...
   within group` in reporting (use `approx_quantiles` or `percentile_cont(...) over ()`),
   `count(*) filter (where ...)` (use `countif`), and `interval '1 day'` in the incremental
   predicate.
3. The 25 analytical queries in `sql/` are written in PostgreSQL dialect and would need a
   BigQuery variant.
4. The ingestion pipeline is not used: BigQuery reads PhysioNet's hosted tables directly.

## Cost control

- Select only the needed columns; MIMIC tables are partitioned and billed by bytes scanned.
- Materialise intermediate models as tables once, then query the marts.
- Set `maximum_bytes_billed` in the profile.

None of the above has been executed in this repository.
