# Local backup/restore and workload evidence

`scripts/verify_restore.py --container revenue-v01-pg-0913` uses
`REVENUE_TEST_DATABASE_URL`, restricted to a loopback `_test` database. Stop writers
first. It takes a custom-format pg_dump, creates a uniquely named new database,
restores there without overwriting an existing database, and compares row counts
and hashes for all eight raw/serving tables. Restored database and dump are retained
for inspection. It intentionally does not transfer database roles/ACLs.

The executed check passed for one raw event, two checkpoints, eight job runs,
three releases, a release pointer, one case, one outbox event and one simulated task.
Backup plus restore/check took 0.445 seconds on this tiny local fixture. This is
not a claimed production RTO/RPO, independent-host recovery, or cloud backup policy.
Restoring original table data preserves observation and publication timestamps;
raw-page replay alone does not. Archive objects and alert audit are separate backups.

`scripts/benchmark_local.py` creates a separate disposable load-test database and
retains it. It writes `reports/benchmark.json` with the measured local result.

Executed workload: 1,000 synthetic CRM opportunities, 500 signed contracts,
100-record ingestion batches, 500 resulting open incidents. Ingestion took 0.712 s;
dbt validation and frozen publication took 3.025 s. Fifty sequential TestClient API
reads had median 9.739 ms and p95 12.316 ms. TestClient bypasses network ingress;
the run is not concurrent, does not include HTTP-source fetching or archive I/O,
and is neither a production SLA nor representative of larger workloads.

Persistent test artifacts: `revenue_restore_3ec8d7562718_test` and
`revenue_load_c822b466048b_test` in the task's PostgreSQL container. No existing
database or backup was overwritten or deleted.
