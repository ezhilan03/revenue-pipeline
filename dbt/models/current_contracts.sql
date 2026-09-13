with ranked as (
    select *, row_number() over (partition by entity_id order by version desc) as rank
    from {{ source('raw', 'events') }} where source = 'contracts'
)
select entity_id as contract_id, payload->>'opportunity_id' as opportunity_id,
    payload->>'status' as status, observed_at, payload_hash
from ranked where rank = 1 and not (payload->>'deleted')::boolean
