{#- Shared banding logic so every model and query uses identical groups. -#}

{% macro age_group(age_col) -%}
    case
        when {{ age_col }} < 18 then '<18'
        when {{ age_col }} < 45 then '18-44'
        when {{ age_col }} < 65 then '45-64'
        when {{ age_col }} < 80 then '65-79'
        else '80+'
    end
{%- endmacro %}


{% macro los_band(los_days_col) -%}
    case
        when {{ los_days_col }} is null then 'Unknown'
        when {{ los_days_col }} < 1 then '<1 day'
        when {{ los_days_col }} < 3 then '1-2 days'
        when {{ los_days_col }} < 7 then '3-6 days'
        when {{ los_days_col }} < 14 then '7-13 days'
        else '14+ days'
    end
{%- endmacro %}


{#- Harmonise MIMIC's granular race strings into broad reporting groups. -#}
{% macro race_group(race_col) -%}
    case
        when {{ race_col }} is null then 'Unknown / not reported'
        when upper({{ race_col }}) like 'WHITE%' or upper({{ race_col }}) = 'PORTUGUESE' then 'White'
        when upper({{ race_col }}) like 'BLACK%' then 'Black'
        when upper({{ race_col }}) like 'HISPANIC%' or upper({{ race_col }}) like '%LATINO%'
            or upper({{ race_col }}) = 'SOUTH AMERICAN' then 'Hispanic / Latino'
        when upper({{ race_col }}) like 'ASIAN%' then 'Asian'
        when upper({{ race_col }}) in ('UNKNOWN', 'UNABLE TO OBTAIN', 'PATIENT DECLINED TO ANSWER')
            then 'Unknown / not reported'
        else 'Other'
    end
{%- endmacro %}
