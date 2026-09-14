# Zero-first deployment decision

Prepared 14 September 2026. Planning only: no billing activation or cloud apply.

## Decision and permission boundary

Default to zero incremental hosting spend. Existing local hardware, electricity
and internet are not free, but this plan adds no cloud subscription charges.
The user's preference for the cheapest fallback is not an approved dollar limit.
Any paid deployment needs a complete estimate, region and explicit approval.

Keep PostgreSQL, Airflow, the API and monitoring in the existing local Docker
setup. Keep standard GitHub-hosted CI on the public repository. Do not replace
Airflow with GitHub Actions and call that a cloud Airflow deployment. Do not use
GitHub runners as a persistent application server or database.

## Options

| Option | Incremental hosting cost | What it proves | Limitation |
| --- | --- | --- | --- |
| Local full stack + public standard CI | $0 | Correctness, orchestration, recovery, reproducible builds | No cloud-operated runtime or always-on public demo |
| Short Azure execution experiment | Not yet fully priced | Cloud identity, image execution and deployment evidence | Requires billing and a separately approved temporary-runtime design |
| Persistent Azure full stack | Not approved or fully priced | Durable cloud operations | Database, scheduler, monitoring, storage and networking must all be sized |

Recommendation: continue the first option while closing local engineering gaps.
Design the second as a bounded experiment, not a replacement for the durable
release. Do not deploy an API pointing at a laptop database over a public tunnel.

## Compute arithmetic, not a deployment quote

For comparison only, use East US retail USD rates retrieved on 14 September 2026.
East US is an estimate location, not an approved deployment region.

Container Apps Consumption active rates returned by the Retail Prices API:

- vCPU: $0.000024 per vCPU-second.
- Memory: $0.000003 per GiB-second.
- Published monthly subscription grants: 180,000 vCPU-seconds and 360,000 GiB-seconds.

A hypothetical job at 1 vCPU / 2 GiB, running 10 minutes daily for 30 days,
uses 18,000 vCPU-seconds and 36,000 GiB-seconds. Gross compute is
18,000 * 0.000024 + 36,000 * 0.000003 = **$0.54/month** before grants.
Compute could be $0 if sufficient subscription-wide grants remain available.
This is an assumed workload, not a measured Azure execution or capacity promise.
It excludes retries, other containers, image startup overhead and every service below.

## Items that must be priced before approval

- Durable PostgreSQL compute, storage and backups, or an explicitly approved
  disposable synthetic experiment. The existing application requires PostgreSQL;
  putting it in an ephemeral container is not a durable deployment solution.
- Airflow control-plane compute and metadata persistence. An alternate scheduler
  changes the release architecture and needs approval.
- Blob capacity, retained versions, soft-deleted data and transactions.
- Private endpoints, private DNS, network integration and any egress/NAT.
  Current `infra/storage/main.tf` disables public network access and supplies no
  private endpoint. It is not an accessible end-to-end archive deployment yet.
  Do not silently weaken this setting to advertise a cheaper price.
- Image registry, logs/retention, monitoring and outbound traffic.
- Terraform state storage and access; tenant/provider availability and taxes.

No whole-stack monthly price is asserted until these line items are resolved.
Do not assume the expired trial includes fresh storage/database allowances.

## Gates for a paid experiment

1. Record the approved region, total experiment ceiling and retention duration.
2. Measure the proposed runtime locally; inventory every billable resource.
3. Produce a dated total estimate, including idle/residual storage and failure retries.
4. Obtain billing/reactivation and resource-creation approval separately.
5. Use short timeouts, bounded retries, limited replicas and no automatic schedule
   for the first run. Configure cost alerts, but never describe them as a hard cap.
6. Record smoke-test and rollback evidence. Review exact cleanup targets with the
   user; retain approved evidence and confirm residual billable resources afterward.

The current archive has `prevent_destroy` and seven-day soft deletion. A blanket
`terraform destroy` is not a guaranteed cleanup or zero-cost strategy. Do not remove
these safeguards without an approved data-retention and teardown decision.

## Sources

- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Container Apps pricing and monthly grants](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
- [Azure Retail Prices API](https://prices.azure.com/api/retail/prices): filter
  `armRegionName eq 'eastus' and serviceName eq 'Azure Container Apps'`,
  Standard vCPU Active Usage and Standard Memory Active Usage, Consumption USD.
- [Azure budget behavior](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets)
