# Release status — 14 September 2026

## Verified local core

- Synthetic HTTP sources; bounded retry, page checkpoints and append-only versions.
- Checksum-addressed archive pages/manifests and integrity-checked resume/replay.
- dbt history and handoff models; validated frozen releases served by API.
- Hourly Airflow: archive/poll -> validate/publish/queue -> simulated dispatch.
- Transactional incident lifecycle and idempotent database-local task delivery.
- Authenticated metrics, Prometheus and Alertmanager firing/recovery audit.
- Provisioned Grafana dashboard and healthy Prometheus datasource; visible stat
  panels confirmed API up, one incident and no pending task backlog.
- 58 passing PostgreSQL-backed tests; nine dbt tests; Docker runtime exercises.
- Separate-database backup/restore fingerprint check and a 1,500-event local load run.
- Terraform private storage foundation validates and passes mocked security checks.

## Not a completed cloud production release

The public repository is [ezhilan03/revenue-pipeline](https://github.com/ezhilan03/revenue-pipeline).
Hosted CI [passed on commit 3ecc647](https://github.com/ezhilan03/revenue-pipeline/actions/runs/34809971237):
Python/PostgreSQL tests, dbt checks, both Docker builds, Airflow DAG loading,
Prometheus rules, and Terraform validation/mocked tests. No Azure credentials
or cloud resources were needed by CI.
No Azure billing activation, Terraform
apply, cloud runtime, private networking or managed production identity is configured.
The Terraform module is storage groundwork, not a complete deployment stack.
Forecasting and AI enrichment remain future milestones; there is no LLM integration
to claim on a resume yet. The current value is operational data engineering.

Production hardening gaps include versioned schema migrations, least-privilege
database roles, request/body limits, retention, cloud-independent backup, source
completeness policies, full HTTP/concurrency load testing and external delivery
adapters. Local static keys and standalone Airflow are development choices.

## Artifacts and state

Runbooks: LOCAL-OPERATIONS.md, MONITORING.md, REPLAY.md, TASK-QUEUE.md, RECOVERY.md.
Earlier dated verification entries are historical; this file is the current summary.
The `revenue-observe` monitoring stack is left running on loopback, with Grafana
at port 3007 and API at 8018. Login uses the locally configured admin credential;
it is not a shared/public service. Airflow/source verification containers are stopped.

Docker cleanup was explicitly approved: only unused images/build cache removed.
All 16 existing containers and 11 existing volumes were preserved at cleanup;
subsequent monitoring setup created its own additional containers/volumes.
Restored and load-test databases, dumps and raw evidence remain available.

## Next authorization boundary

Public repository creation, pushing and hosted CI were explicitly approved and started.
Cloud activation requires a separate region/availability/cost proposal and approval;
none of those actions are covered by local validation or GitHub publication consent.
