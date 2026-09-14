# Retained source pages and recovery

The polling CLI archives decoded source JSON before database validation/commit.
This preserves record values, not exact original HTTP bytes or response headers.
Objects use SHA-256 filenames. Writes flush the file before publishing with a
non-replacing hard link and syncing the directory; a different existing object
is rejected, never overwritten. See [Python filesystem operations](https://docs.python.org/3/library/os.html#os.fsync).
This local POSIX mechanism is not Azure Blob immutability or tamper-proof storage.

```sh
uv run python -m revenue_pipeline.runner --archive-dir reports/raw
```

Each successfully retained page produces an `archive_page` digest in structured
output. Only a completed poll produces `archive_manifest`, containing ordered page
digests. The runner defaults to `reports/raw` or `REVENUE_ARCHIVE_DIR`; Compose
Airflow sets that path inside its persisted metadata volume. Direct `poll()` calls
must explicitly pass an Archive to enable retention.

## Replay

Use an exact digest from the trusted run output. Set `DATABASE_URL` to the intended
initialized local database, stop its live poller, then run:

```sh
uv run python -m revenue_pipeline.archive --archive-dir reports/raw DIGEST
```

Replace `DIGEST` with either a single page or completed-poll manifest digest.
Replay checks all referenced checksums, schemas, source names and cursor continuity
before applying manifest pages. Already committed pages are checked against stored
event hashes; cursor position alone is not treated as proof. Each new page commits
atomically, so a later failure can leave an earlier successful prefix for retry.
Do not reset cursors to bypass a gap. A snapshot beginning at offset 100 cannot
restore an empty source; retain the prior chain or restore the database first.

## Crash and failure cases

- Failed archive write: no source page is committed.
- Archive written, database commit fails: the retained page digest can recover it.
- Database committed, completion manifest missing: replay page digests from the
  logs; identical versions are not duplicated. Re-polling also resumes offsets.
- Malformed records: archived for inspection but never given a completed manifest.
- Corrupted object or manifest gap: replay fails closed.

## Boundaries

This is ingestion recovery, **not point-in-time database restore**. Newly recovered
records get new `observed_at` values; preserving original as-known history requires
database backup/restore. Replaying updates page checkpoint timestamps but does not
create successful live-poll job outcomes. Use full-job metrics, not page times, for
source freshness. Replay does not publish: run the quality wrapper separately.

Checksums prove consistency with a trusted digest, not authenticity. Keep the
archive and its trusted run logs protected. No automatic retention or cleanup is
implemented; objects can outlive failed ingestion. Limit: 8 MiB per object and
1,000 pages per manifest. The existing HTTP client still buffers responses before
archiving, so this is not a streaming/large-payload safety guarantee. Data and
archive must belong to the same synthetic offset-feed identity. Cloud storage,
independent failure-domain backup and historical Airflow backfill remain pending.
