# Approval proposal: temporary Azure demonstration

NOT APPROVED. No subscription upgrade, Azure resource creation or Terraform apply.
This is an alternate demonstration architecture, not silent replacement of the
planned managed-service production release. The local release remains the $0 default.

## Proposed scope

One Linux B2ms VM (2 vCPU, 8 GiB), one 64-GiB Standard SSD OS disk and one Standard
IPv4 address in East US, maximum planned lifetime 24 hours. Run the synthetic stack
on one host; keep application ports loopback-only and access through an SSH tunnel.
Restrict SSH to the operator's current address and use key authentication.
No paid model API, managed PostgreSQL, Container Registry, NAT Gateway, private
endpoint, managed Grafana or Log Analytics workspace is proposed.

This has a single-host failure domain and burstable CPU limits. It is a cloud demo,
not high availability or proof of production sizing. Test actual memory use first;
if this shape is insufficient, stop and revise the proposal rather than resize
silently. Keep LLM inference on the existing local Mac rather than the small VM.

## Dated planning estimate — 14 September 2026, USD

Rates retrieved from the public Azure Retail Prices API, East US Consumption,
Linux (not Windows), excluding Spot and reservations:

| Item | Rate/assumption | Planned 24-hour amount |
| --- | --- | --- |
| B2ms compute | $0.0832/hour x 24 | $1.9968 |
| E6 LRS disk | $4.80/month x 24/730 | $0.1578 |
| E6 LRS mount meter allowance | $0.47/month x 24/730 | $0.0155 |
| Disk operations | $0.002/10,000; assume 500,000 | $0.1000 |
| Standard IPv4 | $0.005/hour x 24 | $0.1200 |
| Base estimate | Sum, rounded | **$2.40** |

This is a usage assumption, not a quote or hard cap. Request approval for **$5 total
for one 24-hour experiment**, including contingency for traffic/operations. Taxes,
currency conversion, quota/region availability and existing subscription grant use
need rechecking. Do not represent the allowance as an Azure-enforced spending cap.
Leaving this configuration running a month would be roughly $69 before operations,
traffic and tax, not $5/month; the proposal is explicitly temporary.

## Required approval before implementation

- Personal Azure billing reactivation and this alternate East US single-VM demo.
- Up to $5 planned total, 24-hour lifetime, no recurring deployment or automatic restart.
- Export evidence/backups, then remove only the new, individually inventoried demo
  resources after the observation window. Existing resources stay untouched.

Before apply: verify account state and current prices; review Terraform plan and
exact resource names; establish timer/cleanup control, cost alerts and backup export.
Auto-shutdown/deallocation alone does not remove disk/IP storage charges. Cleanup
must inventory and remove the approved residual resources and verify their absence.
If these safeguards or the usage estimate cannot be met, do not provision.

## Rate source

[Azure Retail Prices API](https://prices.azure.com/api/retail/prices), with East US
filters for `Virtual Machines BS Series` / `B2ms`, `Standard SSD Managed Disks` /
`E6 LRS`, and `IP Addresses` / `Standard IPv4 Static Public IP`.
This proposal does not count on any free-trial credit.
