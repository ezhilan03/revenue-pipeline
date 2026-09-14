# Latest: Grafana, recovery and Terraform — 13 September 2026

Grafana 12.4.0 provisioned the five-panel revenue dashboard. Datasource health
returned OK and visible stat panels showed API up/one open case/zero pending tasks.
Private storage Terraform validated without warnings and passed mocked security
assertions using AzureRM 4.81.0; no actual Azure plan/apply was run. Full test suite:
58 passed. Local restore and workload measurements are documented in RECOVERY.md.
See RELEASE-STATUS.md for the current whole-project boundary and publishing approval.

# Previous: archive/outbox integration — 13 September 2026

- 58 tests passed, including lifecycle open/resolve/reopen, duplicate publication,
  concurrent dispatch and simulator-failure recovery. Ruff/whitespace checks passed.
- Built `revenue-airflow:local-v06` (`57fbc5532019`) and monitoring image
  `632c6e085f98`. Scheduled and `archive-outbox-verification` DAG runs succeeded.
- Runtime inspection found six retained archive objects, one queued open event
  and exactly one accepted simulated task after both runs. Three-task DAG structure
  check passed. Test Airflow/source containers stopped with evidence preserved.
- Grafana configuration and five dashboard panels implemented; image/runtime and
  visual verification remain pending. Host has 1.9 GiB free. No extra Docker cleanup
  or Grafana image pull performed without further disk-cleanup approval.

# Previous: local raw archive and replay — 13 September 2026

- 55 pytest tests passed; Ruff/whitespace checks passed. Coverage includes
  archived-before-commit recovery, committed-prefix replay, checksum corruption,
  stored-evidence conflicts, invalid records and archive-write failure.
- Actual HTTP polling retained pages/manifests in `reports/raw-verification`.
  CRM manifest: `3b55d0c72d0e5bb87fe859a0a7a2021cc268afc88cd4924d91da687e2be666e5`.
- Stopped the source and replayed that manifest via CLI: zero duplicate inserts.
- Local Python runtime verified; archive support is not yet built into Airflow.
  New observations are not historical restoration. See REPLAY.md for limitations.

Earlier checkpoints below are historical, not the current feature inventory.

# Historical local checkpoint — 13 September 2026

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
# Publication integration and monitoring — 2026-09-13

- Built `revenue-airflow:local-v04` (`6b9e82de56d4`) and ran both a scheduled DAG
  and `publication-verification-0913` successfully through validated publication.
- Live API returned frozen release `bc0f452c-d974-4eb6-8884-ef7b0a76d485`, including
  the synthetic missing-contract incident, cursor metadata and publication time.
- 43 pytest tests passed; Ruff/whitespace checks passed. Promtool validated all
  three alert rules. Hosted GitHub Actions has not been executed.
- Built `revenue-monitoring:local` (`f938698d155f`) and ran the isolated monitoring
  Compose stack. Authenticated Prometheus scraping reported target health `up`.
- Stopped only the monitoring API. `RevenueApiUnavailable` fired, and Alertmanager
  delivered a firing receipt to the SQLite audit sink at 04:03:51 UTC.
- Restarted that API: resolved receipt at 04:04:06 UTC; Prometheus alerts empty.
  No external messages were sent. Demo threshold/retention choices are in MONITORING.md.
- Stopped task-owned Airflow/source after verification. Host had about 2.4 GiB free.
- Grafana, receiver-failure delivery tests, alert-audit retention, raw manifests,
  operational outbox, Terraform and cloud release remain outstanding.

# Validated publication checkpoint — 2026-09-13

- 42 pytest tests passed against PostgreSQL, including real dbt build success and
  a deliberately failing dbt SQL test in a separate temporary project.
- The API now reads frozen serving releases, not live dbt views. Tested initial
  503, raw changes remaining hidden, successful release switching, immutable release
  rows, source-lock exclusion, and pointer-write failure rolling back the new row.
- API/history responses include release ID and publication timestamp. The first
  implementation caps each snapshot collection at 10,000 rows and requires all
  writers/transformers to honor the publication lock protocol.
- Ruff and whitespace checks passed. Built API image `revenue-pipeline:local-v04`
  (prefix `ce152fa1d3ae`). Older Airflow/API containers do not include these changes;
  this publication revision has not yet been rerun through the Airflow image.
- Design references: [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html),
  [dbt build](https://docs.getdbt.com/reference/commands/build).

# Airflow runtime checkpoint — 2026-09-13

- Switched to the official `apache/airflow:slim-3.1.6-python3.12` base and disabled
  uv build caching. Built `revenue-airflow:local-v03`, image
  `sha256:5eb6a05082bb10f70a8708649d583449d4c84ad4c462cf4520e48c2434534f91`.
- Fixed Docker context allowlists: dbt models, DAGs and the validation script now
  enter the image; generated dbt artifacts and secrets remain excluded.
- Fresh-image DAG import/dependency/concurrency assertions passed. The check uses
  the parsed DagBag dictionary and does not require an initialized metadata DB.
- Local standalone Airflow ran against the disposable PostgreSQL test database.
  `scheduled__2026-09-14T03:00:00+00:00` and `local-verification-0913` both succeeded.
- For `local-retry-verification-0913`, deliberately stopped the synthetic source.
  Observed `poll_sources=up_for_retry` while `dbt_quality_gate` had not started.
  Restored the source; final retry and dbt both succeeded at 03:47:41 UTC.
- Stopped the task-owned scheduler and source after the exercise, preserving their
  containers/logs. Other running project containers were left untouched.
- Host free space remained about 3.8 GiB. Hosted CI, historical backfills, atomic
  publication, durable raw manifests, alert delivery and cloud deployment remain
  unverified or unimplemented. Standalone is a local development runtime only.
- Base image reference: [official slim image](https://hub.docker.com/r/apache/airflow/tags/?name=3.1.6&page=1).

# Storage recovery checkpoint — 2026-09-13

With explicit approval, cleared only `/Users/pinkman/.cache/uv` using `uv cache clean`:
3.8 GiB removed, redownloadable dependencies only. Restarted Docker Desktop and
restored the four previously running Revenue, RAG and Recon containers. No volumes,
images, project files or other caches were deleted. Approximately 3 GiB host space
remains, so further large image builds need caution.

After recovery, all 35 pytest cases passed again, the existing API liveness endpoint
responded, and the real quality-wrapper command completed all four dbt models and
nine data tests successfully. Airflow image/runtime verification remains pending;
the successful wrapper run does not prove scheduler execution.

# Orchestration implementation checkpoint — 2026-09-13

- 35 pytest tests passed against real PostgreSQL before the Docker storage failure.
- Ruff passed, including DAG/check-script source. Compose config validation passed.
- Added durable full-job outcomes, authenticated Prometheus-format metrics, a dbt
  build wrapper, hourly Airflow DAG and a separate image using Airflow 3.1.6.
- Tests cover missing/running/failed jobs, retained previous success, partial-page
  failure not reported as full success, metrics auth, and simulated dbt failure.
- Airflow image pull failed extracting a layer with a read-only filesystem error.
  Host disk check then showed only 209 MiB available, 100% capacity. Docker became
  unresponsive and the existing database connection was refused. Disk exhaustion
  is the leading explanation; no Docker restart, prune or user-file deletion was done.
- The subsequent real dbt build wrapper smoke could not connect to PostgreSQL.
  Airflow image build, DAG import check, scheduled execution and hosted CI remain
  UNVERIFIED. Do not interpret unit checks as proof of a working Airflow runtime.
- Resume after host storage recovery: database reachability, pytest/dbt build,
  Airflow image build, check_dag.py, then a real triggered DAG run and retry exercise.

# Local HTTP operation checkpoint — 2026-09-13

- 28 pytest cases passed against the dedicated real PostgreSQL test database.
- 9 dbt data tests passed; Ruff and git diff whitespace checks passed.
- Built `revenue-pipeline:local-v02`, image prefix `de844561ad91`.
- Started the synthetic source in a non-root read-only Docker container with all
  capabilities dropped, loopback-only port 8027 and no-new-privileges enabled.
- Live HTTP liveness succeeded. First real-network runner inserted one CRM version;
  second run inserted zero. Both polled the empty contract source successfully.
- Contract delivery/resolution, invalid offsets, exhausted network retries,
  transient timeout recovery and sanitized failure logging were exercised in tests.
- Source smoke container was stopped after verification. Existing project containers
  were not changed. Hosted CI, Airflow, Terraform and cloud deployment were not run.
- TestClient emits upstream deprecation warnings; tests pass, but compatibility
  maintenance remains. Current dbt views are not an atomic publication gate.
- HTTP retry exception selection follows the [HTTPX exception hierarchy](https://www.python-httpx.org/exceptions/).
