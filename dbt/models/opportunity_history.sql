-- Keep every winning source version at its first observation time. An older
-- version arriving later must not rewrite what was known or become current.
with arrivals as (
    select *, max(version) over (
        partition by entity_id order by observed_at, version
        rows between unbounded preceding and 1 preceding
    ) as previous_max
    from {{ source('raw', 'events') }} where source = 'crm'
), winners as (
    select * from arrivals where previous_max is null or version > previous_max
)
select entity_id as opportunity_id, version, observed_at as known_from,
    lead(observed_at) over (partition by entity_id order by observed_at, version) as known_to,
    (payload->>'effective_at')::timestamptz as source_effective_at,
    (payload->>'deleted')::boolean as deleted,
    payload->>'stage' as stage,
    (payload->>'amount_minor')::bigint as amount_minor,
    payload->>'currency' as currency,
    payload_hash
from winners
