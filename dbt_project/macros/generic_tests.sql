{#- In-house generic tests (no external packages needed, so CI works offline). -#}

{#- Fails for every row where the boolean expression is not true. -#}
{% test expression_is_true(model, expression, where=none, column_name=none) %}
    select * from {{ model }}
    where not ({{ expression }})
    {% if where %} and ({{ where }}) {% endif %}
{% endtest %}


{#- Fails when the model's row count differs from a comparison relation's count. -#}
{% test row_count_equals(model, compare_model, compare_where=none) %}
    with a as (select count(*) as n from {{ model }}),
         b as (select count(*) as n from {{ compare_model }}
               {% if compare_where %} where {{ compare_where }} {% endif %})
    select a.n as model_rows, b.n as compare_rows
    from a cross join b
    where a.n <> b.n
{% endtest %}


{#- Fails for each combination of columns that appears more than once. -#}
{% test unique_combination(model, columns) %}
    select {{ columns | join(', ') }}, count(*) as n
    from {{ model }}
    group by {{ columns | join(', ') }}
    having count(*) > 1
{% endtest %}


{#- Fails when the numeric column falls outside [min_value, max_value]. -#}
{% test value_between(model, column_name, min_value=none, max_value=none) %}
    select * from {{ model }}
    where {{ column_name }} is not null
      and (
        {% if min_value is not none %} {{ column_name }} < {{ min_value }} {% else %} false {% endif %}
        or
        {% if max_value is not none %} {{ column_name }} > {{ max_value }} {% else %} false {% endif %}
      )
{% endtest %}
