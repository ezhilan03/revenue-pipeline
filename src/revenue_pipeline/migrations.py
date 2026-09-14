"""Transactional, forward-only migrations for the local PostgreSQL release."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from revenue_pipeline import schema_v001


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    checksum: str
    apply: Callable


def catalogue():
    return (Migration(1, "baseline", hashlib.sha256(
        Path(schema_v001.__file__).read_bytes()).hexdigest(), schema_v001.apply),)


def migrate(conn, migrations=None):
    """Caller owns the connection. All pending changes and ledger writes are atomic.

    Existing pre-ledger installations are adopted using the idempotent baseline.
    This does not certify arbitrary manual schema modifications as compatible.
    """
    migrations = catalogue() if migrations is None else tuple(migrations)
    if [m.version for m in migrations] != list(range(1, len(migrations) + 1)):
        raise ValueError("Migrations must be contiguous and ordered from version 1")
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout = '5s'")
        conn.execute("SET LOCAL statement_timeout = '30s'")
        conn.execute("SELECT pg_advisory_xact_lock(73000)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS revenue_meta")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revenue_meta.schema_migrations (
                version integer PRIMARY KEY,
                name text NOT NULL,
                checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
            )
        """)
        applied = conn.execute(
            "SELECT version, name, checksum FROM revenue_meta.schema_migrations ORDER BY version"
        ).fetchall()
        if len(applied) > len(migrations):
            raise ValueError("Database is newer than this application; downgrade refused")
        for row, migration in zip(applied, migrations, strict=False):
            if (row["version"], row["name"], row["checksum"]) != (
                migration.version, migration.name, migration.checksum
            ):
                raise ValueError("Migration history mismatch; restore immutable migration files")
        for migration in migrations[len(applied):]:
            migration.apply(conn)
            conn.execute(
                "INSERT INTO revenue_meta.schema_migrations(version, name, checksum) "
                "VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
    return len(migrations) - len(applied)


def main():
    from revenue_pipeline.store import connect

    with connect() as conn:
        count = migrate(conn)
    print(f"Applied {count} schema migration(s)")


if __name__ == "__main__":
    main()
