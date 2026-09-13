# Revenue Pipeline Reliability & Forecasting

An operational data product for a simple but costly handoff: **CRM says closed-won,
but there is no signed contract in the contract system.** All examples are synthetic.

The first implemented slice ingests source versions, preserves as-known deal
history, models the mismatch in dbt and serves an authenticated investigation API.
It is local development, not a completed production release. Forecasting, AI,
automated tasks, Airflow, Blob storage and Azure deployment are not implemented yet.

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
uv run dbt build --project-dir dbt --profiles-dir dbt
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
```

The dbt models are views in this slice: the next API read has no open exception.
Replaying the seed does not duplicate source versions. It does not erase a
previously delivered contract; use a separate clean development database to
restart the scenario.

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
Tests truncate only this project's raw tables in that database. Never point them
at a development environment whose records you want to retain.

```sh
export REVENUE_TEST_DATABASE_URL='postgresql://revenue:local-test-password@127.0.0.1:55447/revenue_test'
uv run pytest -q
uv run ruff check .
```

The test fixture builds dbt views against real PostgreSQL before API/integration
tests. GitHub Actions config adds data tests and a Docker image build; a workflow
file is not evidence of a successful hosted run. The API image deliberately omits
dbt/test dependencies; a separate orchestration image is still required.

## Planned deployment

Azure Blob raw landing → Python ingestion → PostgreSQL/dbt → Container Apps API.
Airflow will coordinate intervals, retries, backfills and model publication.
Terraform, scoped identity, CI/CD, operational alerts and measured recovery are
required before the first cloud release. Account, region and spending approval
remain outstanding. See [release plan](docs/RELEASE-PLAN.md).
