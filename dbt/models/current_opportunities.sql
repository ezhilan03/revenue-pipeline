select * from {{ ref('opportunity_history') }} where known_to is null and not deleted
