from dataclasses import replace

import pytest

from revenue_pipeline.migrations import Migration, catalogue, migrate
from revenue_pipeline.store import connect


@pytest.fixture
def migration_connection():
    # Each test's DDL/ledger changes stay in a rolled-back outer transaction.
    conn = connect()
    conn.execute("SELECT 1")
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def test_repeat_does_not_reapply_or_change_ledger(migration_connection):
    conn = migration_connection
    before = conn.execute("SELECT * FROM revenue_meta.schema_migrations").fetchall()
    assert migrate(conn) == 0
    assert conn.execute("SELECT * FROM revenue_meta.schema_migrations").fetchall() == before


def test_changed_baseline_fails_closed(migration_connection):
    with pytest.raises(ValueError, match="history mismatch"):
        migrate(migration_connection, [replace(catalogue()[0], checksum="changed")])


def test_adopt_legacy_schema_preserves_checkpoint(migration_connection):
    conn = migration_connection
    conn.execute("DELETE FROM revenue_meta.schema_migrations")
    conn.execute("INSERT INTO revenue_raw.checkpoints(source, cursor) VALUES ('crm', 23)")
    assert migrate(conn) == 1
    assert conn.execute("SELECT cursor FROM revenue_raw.checkpoints").fetchone()["cursor"] == 23
    assert migrate(conn) == 0


def test_newer_database_refuses_old_application(migration_connection):
    with pytest.raises(ValueError, match="downgrade refused"):
        migrate(migration_connection, [])


def test_missing_version_refused(migration_connection):
    with pytest.raises(ValueError, match="contiguous"):
        migrate(migration_connection, [replace(catalogue()[0], version=2)])


def test_upgrade_preserves_existing_data(migration_connection):
    conn = migration_connection
    conn.execute("INSERT INTO revenue_raw.checkpoints(source, cursor) VALUES ('crm', 17)")
    addition = Migration(2, "test_addition", "test-only", lambda c: c.execute(
        "CREATE TABLE revenue_meta.upgrade_probe (id integer PRIMARY KEY)"))
    assert migrate(conn, [*catalogue(), addition]) == 1
    assert conn.execute("SELECT cursor FROM revenue_raw.checkpoints").fetchone()["cursor"] == 17
    assert migrate(conn, [*catalogue(), addition]) == 0


def test_failed_batch_rolls_back_ddl_and_ledger(migration_connection):
    conn = migration_connection

    def fail(c):
        c.execute("CREATE TABLE revenue_meta.failure_probe (id integer)")
        raise RuntimeError("injected migration failure")

    second = Migration(2, "addition", "test-only", lambda c: c.execute(
        "CREATE TABLE revenue_meta.upgrade_probe (id integer)"))
    third = Migration(3, "failure", "test-only", fail)
    with pytest.raises(RuntimeError, match="injected"):
        migrate(conn, [*catalogue(), second, third])
    assert conn.execute("SELECT to_regclass('revenue_meta.upgrade_probe') AS table").fetchone()[
        "table"] is None
    assert conn.execute("SELECT to_regclass('revenue_meta.failure_probe') AS table").fetchone()[
        "table"] is None
    assert conn.execute("SELECT count(*) AS n FROM revenue_meta.schema_migrations").fetchone()[
        "n"] == 1
