select o.opportunity_id, o.version as crm_version, o.amount_minor, o.currency,
    o.known_from, o.payload_hash as crm_evidence_hash,
    'closed_won_without_signed_contract'::text as reason
from {{ ref('current_opportunities') }} o
where o.stage = 'closed_won'
and not exists (
    select 1 from {{ ref('current_contracts') }} c
    where c.opportunity_id = o.opportunity_id and c.status = 'signed'
)
