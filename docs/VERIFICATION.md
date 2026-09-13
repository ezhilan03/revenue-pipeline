# Local checkpoint — 13 September 2026

## Verified

- Python 3.12 dependency lock generated; `uv sync --frozen` used by image/CI configuration.
- `ruff check .` passed; Python compile check passed.
- 20 pytest tests passed against an isolated PostgreSQL 16.9 database, including
  transaction rollback, replay, concurrent checkpoint exclusion, contract
  cancellation/deletion, late versions, strict source contracts and API auth.
- `dbt build`: 4 views built and 9 data tests passed.
- API Docker image built as `revenue-pipeline:local-v01`, image ID prefix
  `c579095ba263`, with non-root runtime and locked application dependencies.
- Live loopback HTTP smoke test from the Docker API returned one missing-contract
  exception for synthetic `demo-001` (GBP 12,500). After contract delivery, the
  API returned an empty exception list; the CRM seed replay inserted zero rows.

Database: task-owned `revenue-v01-pg-0913`, loopback port 55447, disposable
`revenue_test`. API: task-owned `revenue-v01-api-0913`, loopback port 8017.
The API and database are left running for local inspection. They contain synthetic
fixtures only. Do not run the truncating test suite against records you want kept.

## Limitations / not verified

- No GitHub push, hosted CI, published image or Azure deployment.
- No Airflow, Blob landing, Terraform apply, forecast model, AI enrichment,
  task outbox, external alert delivery, backup/restore, load benchmark or SLA.
- Current dbt outputs are live views, not atomically published forecast releases.
- Test-only authentication and database owner role are not the cloud access model.
- Two dependency deprecation warnings in the FastAPI/Starlette test client remain;
  they did not fail the test suite. Resolve compatibility before release locking.
- Docker Desktop initially left the database/API containers in created state;
  explicit `docker start` succeeded, after which readiness and HTTP checks passed.
  No changes were made to other projects' containers or Docker configuration.
