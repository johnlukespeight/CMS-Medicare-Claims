{#
    Standard dbt override: use a model's `+schema` config verbatim (e.g.
    "medicare_marts") instead of dbt's default "<target_dataset>_<custom>"
    prefixing behavior. Without this, marts would land in a dataset named
    "medicare_staging_medicare_marts" instead of "medicare_marts".
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
