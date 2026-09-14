# Database capability roles

This is tested provisioning groundwork, not a claim that the running Compose
services already use separate identities. Current development services still
use their configured database owner credential. No login/password is created by
this tool, and no existing runtime credential is changed.

## Permissions

| Profile | Allowed | Explicitly withheld |
| --- | --- | --- |
| ingest | Read/append raw events, maintain checkpoints and job outcomes | Raw update/delete/truncate, serving data, migrations |
| transform | Read sources, own/replace four dbt views, publish releases/cases/outbox, track jobs | Raw mutation, release deletion, delivery acknowledgement, migrations |
| api | Read frozen releases/cases and job health; count pending outbox delivery | Raw payloads, outbox payloads, all writes and migrations |
| dispatch | Read outbox, update only delivered_at, append/read simulated tasks | Rewrite outbox payload, read raw events, publish cases |

No new role gets SUPERUSER, CREATEDB, CREATEROLE, REPLICATION or BYPASSRLS.
Roles are NOLOGIN capability groups. Names include a hash of the database name
because PostgreSQL roles are cluster-wide. Existing matching names cause a refusal,
not silent reuse of potentially overprivileged roles. No broad default privileges
are granted; future tables require explicit permission review.

The transform role intentionally combines dbt and publication privileges because
the current quality command does both. Ingestion profiles are not source-isolated:
they can maintain both CRM and contract checkpoints. Job status access is likewise
not row-isolated. These limits are documented rather than claiming per-job RLS.

## Explicit one-time setup

Stop this project's writers and back up the target first. Initialize migrations
and dbt models using the development owner before adoption. Use an appropriately
privileged provisioning identity; existing view ownership transfer may require a
superuser or equivalent ownership/membership authority. Then run:

```sh
uv run python -m revenue_pipeline.database_roles --expected-database revenue
```

`DATABASE_URL` must name that exact database. The operation creates four roles,
grants explicit privileges and transfers only the four named dbt views in the
`revenue` schema to the transform role. A model with a non-view object type causes
rollback. The full provisioning transaction is atomic and uses the migration lock.
This is NOT part of startup and is NOT an idempotent grants reconciler.

Before using a non-pristine database, audit PUBLIC grants, existing group
memberships, security-definer functions and database/schema creation privileges.
This tool neither certifies nor revokes inherited privileges from arbitrary legacy
configuration. The tests use the project's PostgreSQL 16 test setup.

## Runtime activation still required

1. Create separate restricted LOGIN identities through a secure credential channel.
   Give each only its matching capability membership and required database CONNECT.
   Do not give any runtime login membership in the owner or migration role.
2. Keep provisioning/migration credentials outside application containers.
3. Start the API with its own `DATABASE_URL`; run source, quality and dispatcher
   processes with their respective DSNs. dbt inherits the quality process DSN.
4. The current standalone Airflow setup shares an environment and OS identity:
   merely putting four passwords into it is not task credential isolation. A real
   isolated worker/secret-delivery design is still needed before claiming that.
5. Verify real authenticated connections, dbt replacement, publication, API reads
   and dispatch end to end; rerun negative checks, then retire the owner credential.

No automatic login provisioning, secret distribution, credential rotation, worker
isolation or live service switch is performed by this change.

## Verification

22 real PostgreSQL tests use `SET LOCAL ROLE` to verify allowed and forbidden SQL,
dbt-view access/creation, wrong-database refusal and role-name collision refusal.
Role creation, grants and ownership changes are rolled back per test. This verifies
database authorization, not password authentication or a live deployment cutover.
