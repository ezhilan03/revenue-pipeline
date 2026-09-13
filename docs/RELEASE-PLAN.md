# Independent Azure release plan

## Ownership and scope

This workspace owns the new Revenue project. Recon and Fintech RAG improvements
remain in the existing project-building chat; do not modify their implementation.
The current user request authorizes beginning this new project despite older
roadmap ordering. Do not delete older project ideas or metrics.

## Value beyond a dashboard

Detect operational handoff failures across CRM, contracts, activation, invoices
and payments. Provide an evidence-backed queue that an operator can act on;
preserve the history needed to explain forecast changes. Bookings, invoicing and
cash stay distinct. Begin with CRM/contract mismatch, then expand one source at
a time. An attractive dashboard alone does not satisfy the project.

## Milestones

1. **Local correctness slice:** strict source contracts, paginated/retry ingestion,
   transactional checkpoints, immutable source versions, as-known dbt history,
   missing-contract model and authenticated API. Exercise replay, corrections,
   deletion, concurrency and recovery from source failure against real PostgreSQL.
2. **Operated local pipeline:** simulator HTTP service, Airflow interval/backfill
   DAG, dbt quality/publication gates, immutable raw objects and manifest protocol,
   durable exception lifecycle and idempotent simulator-only task outbox. Add
   structured logs, freshness/completion metrics and alert firing/delivery/recovery.
3. **Azure release:** reviewed cost/access design; Terraform state bootstrap;
   separate app/ingest/transform roles; protected CI deployment; immutable image
   digest; Blob, registry, PostgreSQL and Container Apps; persistent Airflow control
   plane or explicitly approved alternate design. Authenticated smoke tests,
   backup/restore, rollback and a timed observation window complete the release.
4. **Forecasting and bounded AI:** append activation/invoice/payment contracts;
   point-in-time forecasting with temporal holdouts and per-currency outputs.
   Compare stage-weighted and historical cohort baselines. Record why forecasts
   changed. Optional local-model note extraction/explanation must cite facts,
   pass frozen evaluation cases, and never mutate totals or block the cloud pipeline.

## History decision

Store immutable event versions and model winning as-known versions directly in
dbt. Do not make periodic snapshots the only source of truth: missed runs and
late delivery would lose detail. This is a bounded source-version/observation
history, not a fully general bitemporal accounting system or a forecast product.
Record publication time separately when materialized forecast releases arrive.

## Release design decisions awaiting user input

- Azure subscription/tenant, approved region, and whether a personal subscription
  already exists. Never use employer billing/access.
- Monthly spending target and acceptable always-on versus demo availability.
  An always-on Airflow control plane and database need explicit sizing; do not
  reuse the other chat's AWS estimate. Budget alerts are not a hard spending cap.
- Public GitHub repository name/visibility and preferred external alert destination.

These do not prevent local implementation. Do not apply Terraform, create paid
resources, publish employer artifacts or send notifications without scoped approval.

## Engineering bar before claiming production-grade

Use a declared workload; lock dependencies and tested images; authenticated TLS;
least-privilege identities and secret management; migrations; retries/quarantine;
source completeness and freshness signals; timeout and concurrency limits;
actual alerts; retention; measured RTO/RPO; backup/restore; image rollback and a
schema forward-fix policy. Execute load tests and record costs/limitations. A local
test count is progress, not proof of a cloud-operated production service.

## References checked for design

- [dbt history/snapshot semantics](https://docs.getdbt.com/docs/build/snapshots)
- [PostgreSQL advisory locking](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [Azure Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
