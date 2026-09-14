import pytest
from psycopg import errors, sql

from revenue_pipeline.database_roles import provision
from revenue_pipeline.store import connect


@pytest.fixture
def capabilities():
    conn = connect()
    conn.execute("SELECT 1")
    database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
    try:
        roles = provision(conn, database)
        yield conn, roles
    finally:
        # Role creation, grants and ownership changes never escape the test transaction.
        conn.rollback()
        conn.close()


def assume(conn, role):
    conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))


@pytest.mark.parametrize("profile,statement", [
    ("api", "SELECT data FROM revenue_serving.releases"),
    ("api", "SELECT count(*) FROM revenue_serving.outbox WHERE delivered_at IS NULL"),
    ("ingest", "INSERT INTO revenue_raw.checkpoints(source,cursor) VALUES ('crm',1)"),
    ("transform", "CREATE VIEW revenue.permission_probe AS SELECT * FROM revenue_raw.events"),
    ("transform", "SELECT * FROM revenue.closed_won_without_contract"),
    ("dispatch", "SELECT event_key,payload FROM revenue_serving.outbox FOR UPDATE SKIP LOCKED"),
    ("dispatch", "UPDATE revenue_serving.outbox SET delivered_at=clock_timestamp()"),
])
def test_permitted_operations(capabilities, profile, statement):
    conn, roles = capabilities
    assume(conn, roles[profile])
    conn.execute(statement)


@pytest.mark.parametrize("profile,statement", [
    ("api", "DELETE FROM revenue_serving.cases"),
    ("api", "SELECT payload FROM revenue_raw.events"),
    ("api", "SELECT payload FROM revenue_serving.outbox"),
    ("ingest", "UPDATE revenue_raw.events SET version=2"),
    ("ingest", "TRUNCATE revenue_raw.events"),
    ("ingest", "SELECT * FROM revenue_serving.releases"),
    ("transform", "INSERT INTO revenue_raw.checkpoints(source,cursor) VALUES ('crm',1)"),
    ("transform", "DELETE FROM revenue_serving.releases"),
    ("transform", "UPDATE revenue_serving.outbox SET delivered_at=clock_timestamp()"),
    ("dispatch", "UPDATE revenue_serving.outbox SET payload='{}'::jsonb"),
    ("dispatch", "SELECT * FROM revenue_raw.events"),
    ("api", "SELECT * FROM revenue_meta.schema_migrations"),
    ("api", "CREATE TABLE revenue_serving.permission_probe(id integer)"),
])
def test_forbidden_operations(capabilities, profile, statement):
    conn, roles = capabilities
    assume(conn, roles[profile])
    with pytest.raises(errors.InsufficientPrivilege):
        conn.execute(statement)


def test_role_collision_fails_closed(capabilities):
    conn, _ = capabilities
    database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
    with pytest.raises(ValueError, match="already exists"):
        provision(conn, database)


def test_wrong_target_refused(capabilities):
    conn, _ = capabilities
    with pytest.raises(ValueError, match="does not match"):
        provision(conn, "not-the-selected-database")
