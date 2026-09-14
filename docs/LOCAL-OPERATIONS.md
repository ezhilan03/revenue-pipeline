# Local orchestration runbook

## Scope and safety

This is a synthetic, local-only Airflow development instance. Azure billing stays
disabled. Airflow standalone uses a persisted local metadata directory; it is not
the cloud control-plane design. Bind the UI only to loopback. Never expose its
development credentials or use employer source data.

Use a dedicated Compose database for this flow, not the direct-seed demo or a test
database while tests are running. The source offset log must not be interchanged.

## Start

Set `PGPASSWORD` to a local-only URL-safe password (the Compose DSN embeds it).
Run from the repository root:

```sh
docker compose -p revenue-dev --profile sources --profile orchestration up -d --build
docker compose -p revenue-dev exec airflow /opt/revenue/.venv/bin/python -c 'from revenue_pipeline.store import initialize; initialize()'
docker compose -p revenue-dev exec airflow python /opt/revenue/check_dag.py
docker compose -p revenue-dev exec airflow airflow dags unpause revenue_hourly
docker compose -p revenue-dev exec airflow airflow dags trigger revenue_hourly
```

The DAG starts paused so schema initialization happens before polling. The UI is
at `http://127.0.0.1:8087`; inspect the local standalone logs for its login details.
Do not paste passwords into GitHub issues or shared screenshots.

The sequence is `poll_sources -> dbt_quality_gate`, with two task retries, bounded
execution time and one active DAG run. Successful source pages survive a retry;
the next attempt resumes their offsets. The quality command uses `DATABASE_URL`
for both jobs, overriding stale PG environment values.

## Recovery is not historical backfill

Clearing/retrying a failed task resumes the current append-only source feed.
`catchup=False` intentionally avoids pretending a historical Airflow logical date
retrieves historical source state. Historical interval replay needs retained raw
objects and a manifest contract; it is not implemented. Do not reset checkpoints
or run the direct-seed demo against this database.

## Monitoring

The application `/metrics` route requires `X-API-Key`, just like its data routes.
It emits Prometheus text for the fixed jobs `crm`, `contracts`, and `quality`:

- `revenue_job_success`: latest attempt succeeded; missing/running/failed is zero.
- `revenue_job_last_success_timestamp_seconds`: last completed success or zero.
- `revenue_job_running`: latest attempt has started but has not finished.

Missing sources must not be interpreted as healthy. A process killed mid-job
leaves a running row; its last-success age continues increasing. An initial hourly
demo freshness threshold is two hours, subject to observed workload. Collectors
must also alert on failed scrapes (`up == 0`); database failure makes the endpoint
fail, rather than fabricating healthy values. Metrics are implemented;
Prometheus and local Alertmanager delivery are configured in the separate
[monitoring stack](MONITORING.md). Grafana dashboards are not implemented yet.

The older API `source_freshness` value is the most recent committed **page**, not
full-poll completion. Use the new job metrics to assess full completion.

## Validated publication and limits

The quality wrapper holds session advisory locks for both source writers, executes
`dbt build`, then atomically inserts a frozen JSON dataset and switches the active
release pointer. Both API data routes read that pointer with its dataset in a single
query. Validation or pointer-update failure leaves the last release available;
no release means HTTP 503. Responses include release ID and publication time.
Direct `dbt build` does not publish. Re-run the quality wrapper after new ingestion.

Snapshots contain exceptions, opportunity history and source cursors/page timestamps.
They are append-only at the database trigger level; a privileged owner can bypass
controls. Live job metrics are independent of the frozen publication metadata.
Both endpoints are internally consistent; separate requests can see different
releases, so clients must compare release IDs when combining responses.

This first implementation deliberately caps each snapshot collection at 10,000
rows and blocks compliant ingestion during validation (dbt timeout: ten minutes).
Use only the wrapper for transformations; ad-hoc dbt/SQL writers outside the lock
protocol are not coordinated. Larger workloads need staged partitioned releases,
not an ever-growing JSON snapshot. Model tests do not establish source completeness;
full-poll health, manifests, retention, rollback controls and least-privilege roles
remain separate requirements. No automatic release deletion is configured.

## Stop without deleting data

```sh
docker compose -p revenue-dev --profile sources --profile orchestration stop
```

Do not use `down -v` unless you intend to discard the local database and Airflow
metadata. The Docker images are version-tagged, not digest-pinned release images.

References: [Airflow standalone](https://airflow.apache.org/docs/apache-airflow/3.1.6/start.html),
[DAG dependencies](https://airflow.apache.org/docs/apache-airflow/3.1.6/core-concepts/dags.html),
[Prometheus exposition](https://prometheus.io/docs/instrumenting/exposition_formats/).
