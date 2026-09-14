# Revenue Pipeline Reliability & Forecasting

[![Revenue checks](https://github.com/ezhilan03/revenue-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ezhilan03/revenue-pipeline/actions/workflows/ci.yml)

Current evidence and unfinished release gates: [release status](docs/RELEASE-STATUS.md).

An operational data product for a simple but costly handoff: **CRM says closed-won,
but there is no signed contract in the contract system.** All examples are synthetic.

The first implemented slice ingests source versions, preserves as-known deal
history, models the mismatch in dbt and serves an authenticated investigation API.
It is local development, not a completed production release. Forecasting, AI,
cloud Blob integration and Azure deployment are not implemented yet. Local task
dispatch, raw replay, validated publication and monitoring are implemented.
An hourly Airflow DAG, scheduler quality gate and authenticated job metrics now
exist. Local scheduled and manually triggered Airflow runs have passed against
PostgreSQL. This verifies a development scheduler, not a production deployment.

## Run locally

Requires Python 3.12, uv and Docker. Use your own local-only password and API key;
do not commit them. The database port is bound to loopback.

```sh
export PGPASSWORD='choose-a-local-password'
export DATABASE_URL="postgresql://revenue:${PGPASSWORD}@127.0.0.1:55447/revenue"
export REVENUE_API_KEY='choose-a-local-api-key'
docker compose -p revenue-dev up -d --wait
uv sync --frozen
uv run python -m revenue_pipeline.demo
uv run python -m revenue_pipeline.quality
uv run uvicorn revenue_pipeline.api:app --host 127.0.0.1 --port 8017
```

In another terminal with the same API key:

```sh
curl -H "X-API-Key: $REVENUE_API_KEY" http://127.0.0.1:8017/exceptions
```

The queue contains synthetic opportunity `demo-001`, GBP 12,500 (1,250,000 minor
units). Deliver the missing signed contract:

```sh
uv run python -m revenue_pipeline.demo --deliver-contract
uv run python -m revenue_pipeline.quality
```

The quality command validates and publishes a frozen release: the next API read
has no open exception. Ingestion or direct `dbt build` alone does not publish.
Replaying the seed does not duplicate source versions. It does not erase a
previously delivered contract; use a separate clean development database to
restart the scenario.

## Poll a real local HTTP source

Point `DATABASE_URL` at a separate empty development database, not the seeded
demo above. Initialize its tables, then start the synthetic source:

```sh
uv run python -c 'from revenue_pipeline.store import initialize; initialize()'
uv run uvicorn revenue_pipeline.simulator:from_environment --factory --host 127.0.0.1 --port 8027
```

Run the bounded ingestion job with the same `DATABASE_URL`:

```sh
uv run python -m revenue_pipeline.runner
```

The job polls both feeds, resumes committed offsets, emits JSON run/source outcomes
and exits nonzero on failure. Repeat runs do not duplicate versions. This is a job
entrypoint, not an installed scheduler or a model publication gate.

To deliver the contract, stop only the simulator process and restart it with
`SIMULATOR_DELIVER_CONTRACT=1` preceding the same uvicorn command, then rerun the
job. The fixed fixture adds the contract without changing the CRM prefix. Reverting
the fixture after consumption returns HTTP 409 rather than silently resetting a
checkpoint. Do not mix the direct-seed demo and HTTP feed in the same database:
they have different offset logs. Use a separate initialized database for each.

Alternatively, `docker compose -p revenue-dev --profile sources up -d --build simulator`
runs the source in a non-root, read-only container on loopback port 8027. The source
has synthetic data only and no public authentication; do not deploy it publicly.

## Data correctness

- Source contract: append-only offset feed; each entity has immutable, increasing
  version numbers. This is a simulator protocol, not a claim to support Salesforce
  or another real vendor's pagination/CDC semantics.
- Raw event versions and ingestion cursors commit atomically in PostgreSQL.
- A source-level advisory transaction lock excludes conflicting checkpoint writes.
- Identical source-version replay is a no-op; changed content under the same
  version fails the entire page without advancing the cursor.
- Raw UPDATE/DELETE operations are rejected by a trigger. A privileged database
  owner can bypass controls; cloud roles, WORM objects and retention are release gates.
- Strict typed records reject floating-point money, unknown fields and naive dates.
- Deal history separates source effective time from first observation time. Late
  lower versions remain raw evidence without overriding current state. It records
  ingestion knowledge, not when downstream users first saw a published model.
- Contracts must be signed and not deleted; draft, cancelled or unrelated contracts
  cannot conceal a missing handoff. No cross-currency totals or FX assumptions.
- Failure retries are bounded. Successful pages persist so a later poll resumes;
  malformed pages fail closed rather than silently dropping a record.

## API

`GET /health/live` is liveness only, not database/model readiness.
`GET /exceptions` returns an evidence hash, deal/version, amount/currency and source
poll timestamps. Missing sources are absent from freshness rows, not implicitly
healthy. `GET /opportunities/{id}/history` returns as-known source-version history.
Both data routes require `X-API-Key`; missing server configuration fails closed.
Static-key authentication is local/demo scope. No production ingress, TLS, rate
limits, pooling or token identity claims are made.

## Verify

Tests require a **dedicated disposable PostgreSQL database whose name ends `_test`**.
Tests truncate this project's raw and serving tables in that database. Never point them
at a development environment whose records you want to retain.

```sh
export REVENUE_TEST_DATABASE_URL='postgresql://revenue:local-test-password@127.0.0.1:55447/revenue_test'
uv run pytest -q
uv run ruff check .
```

The test fixture builds dbt views against real PostgreSQL before API/integration
tests. GitHub Actions config adds data tests and a Docker image build; a workflow
file is not evidence of a successful hosted run. The API image deliberately omits
dbt/test dependencies; `Dockerfile.airflow` supplies the separate orchestration image.

## Planned deployment

The polling CLI now retains checksum-addressed source pages and completed-poll
manifests. See [replay and recovery](docs/REPLAY.md) for resume rules and limits.

Local Prometheus scraping, Alertmanager routing and an authenticated notification
audit sink are available in [the monitoring runbook](docs/MONITORING.md).
Notifications stay local. Grafana's provisioned dashboard is verified locally;
external paging is not configured. See [task queue](docs/TASK-QUEUE.md) and
[recovery checks](docs/RECOVERY.md) for additional operational evidence.

See [local operations](docs/LOCAL-OPERATIONS.md) for the new orchestration setup,
recovery semantics, metrics and the distinction between a scheduler quality gate
and atomic publication. See the verification record for executed checks and gaps.

Azure Blob raw landing → Python ingestion → PostgreSQL/dbt → Container Apps API.
Airflow will coordinate intervals, retries, backfills and model publication.
The [Terraform storage foundation](infra/storage/README.md) passes local validation
and mocked security checks, but has not been applied. Full cloud networking,
compute, identity, deployment pipeline and spending approval remain outstanding.
See [release plan](docs/RELEASE-PLAN.md).
