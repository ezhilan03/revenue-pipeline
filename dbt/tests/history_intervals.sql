select * from {{ ref('opportunity_history') }}
where known_to < known_from or amount_minor < 0
