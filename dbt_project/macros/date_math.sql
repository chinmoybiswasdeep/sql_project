{#- Fractional time differences, dispatched per adapter so models stay portable
    between PostgreSQL (primary) and BigQuery (optional backend). -#}

{% macro hours_between(start_ts, end_ts) -%}
    {{ return(adapter.dispatch('hours_between')(start_ts, end_ts)) }}
{%- endmacro %}

{% macro default__hours_between(start_ts, end_ts) -%}
    (extract(epoch from ({{ end_ts }} - {{ start_ts }})) / 3600.0)
{%- endmacro %}

{% macro bigquery__hours_between(start_ts, end_ts) -%}
    (timestamp_diff({{ end_ts }}, {{ start_ts }}, second) / 3600.0)
{%- endmacro %}


{% macro days_between(start_ts, end_ts) -%}
    ({{ hours_between(start_ts, end_ts) }} / 24.0)
{%- endmacro %}


{% macro add_hours(ts, hours) -%}
    {{ return(adapter.dispatch('add_hours')(ts, hours)) }}
{%- endmacro %}

{% macro default__add_hours(ts, hours) -%}
    ({{ ts }} + ({{ hours }}) * interval '1 hour')
{%- endmacro %}

{% macro bigquery__add_hours(ts, hours) -%}
    timestamp_add({{ ts }}, interval {{ hours }} hour)
{%- endmacro %}


{% macro year_of(ts) -%}
    cast(extract(year from {{ ts }}) as integer)
{%- endmacro %}


{#- Readmission window in hours, from project var readmission_window_days. -#}
{% macro readmission_window_hours() -%}
    {{ return(var('readmission_window_days', 30) * 24) }}
{%- endmacro %}
