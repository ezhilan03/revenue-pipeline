# PostgreSQL schema migrations

`initialize()` now applies a forward-only migration catalogue. With `DATABASE_URL`
set to the intended database, the explicit command is:

```sh
uv run python -m revenue_pipeline.migrations
```

Version, name, SHA-256 source-file checksum and application timestamp are stored in
`revenue_meta.schema_migrations`. Keep applied migration files immutable, including
whitespace. Add subsequent changes as separate files and append contiguous versions
to `catalogue()`. Each file must contain its schema changes rather than delegating
them to mutable external helpers. Unknown/newer database history or changed applied
files fail closed before pending migrations execute.

The complete pending batch and its ledger updates share one transaction. Failures
roll back DDL and ledger together. Advisory transaction lock 73000 serializes
migration runners; lock waits are bounded at five seconds and each SQL statement at
30 seconds. These are not a total runtime limit on Python callbacks. Operations
that cannot run in a PostgreSQL transaction need a separately reviewed protocol.

## Existing installations

Version 1 is the old idempotent schema bootstrap, preserved in `schema_v001.py`.
It can adopt an existing pre-ledger development database without dropping tables
or changing event/checkpoint data. It reinstalls the existing immutability triggers.
It does NOT compare every existing column, constraint or manually altered object
with an expected schema. Only adopt a known-compatible project database. Unknown
schema drift requires inspection; a ledger entry is not a schema-drift certificate.

## Release procedure and limits

1. Stop the project's writers, scheduler and API before an upgrade; the migration
   advisory lock is not a general application maintenance lock.
2. Back up and verify restore to a separate database. The restore fingerprint
   inventory now includes the migration ledger.
3. Run migrations with an explicitly selected migration-capable role.
4. Run dbt build and release smoke tests, then resume the application.
5. On failure retain evidence and forward-fix. No automatic down migrations or
   destructive reset is provided. Application rollback must be compatible with
   the recorded schema version; older catalogues are refused.

Runtime/migration role separation, full schema-drift validation and zero-downtime
expand/contract deployment remain open release gates. The local demo still calls
`initialize()` for convenience; this is not a production privilege recommendation.

## Local verification — 14 September 2026

65 tests passed, including seven migration cases: repeat/no-op, altered checksum,
legacy adoption preserving a checkpoint, newer database refusal, version-gap
refusal, additive upgrade preserving data, and failed-batch DDL/ledger rollback.
The backup/restore smoke passed all nine table fingerprints including the ledger
in a separate disposable database. This was a tiny fixture, not an RTO benchmark.
