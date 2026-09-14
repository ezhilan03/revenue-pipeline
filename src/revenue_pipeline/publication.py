"""Small-workload frozen releases; source writers must honor the shared lock protocol."""
from contextlib import contextmanager
from uuid import uuid4

from psycopg import sql
from psycopg.types.json import Jsonb

from revenue_pipeline.forecast import forecast
from revenue_pipeline.outbox import sync_cases
from revenue_pipeline.store import connect


@contextmanager
def publication_lock():
    # A dedicated session owns both source locks across dbt's independent connections.
    # Do not hold table read locks while dbt replaces views.
    with connect() as conn:
        conn.autocommit = True
        conn.execute("SET statement_timeout = '15s'")
        conn.execute("SELECT pg_advisory_lock(73001)")
        conn.execute("SELECT pg_advisory_lock(73002)")
        yield conn
        # Closing the connection releases session locks even on validation failure.


def capture_release(conn):
    """Internal: call only after dbt build succeeds while publication_lock is held."""
    data = {}
    for key, schema, table, order in (
        ("items", "revenue", "closed_won_without_contract", "opportunity_id"),
        ("history", "revenue", "opportunity_history", "known_from"),
        ("source_freshness", "revenue_raw", "checkpoints", "source"),
    ):
        rows = conn.execute(sql.SQL(
            "SELECT to_jsonb(r) AS value FROM {}.{} r ORDER BY {} LIMIT 10001"
        ).format(sql.Identifier(schema), sql.Identifier(table), sql.Identifier(order))).fetchall()
        if len(rows) > 10000:
            raise ValueError("Local release limit exceeded; previous release retained")
        data[key] = [row["value"] for row in rows]
    as_of = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
    data["forecast"] = forecast(data["history"], as_of)
    release_id = uuid4()
    with conn.transaction():
        conn.execute("INSERT INTO revenue_serving.releases(release_id,data) VALUES (%s,%s)",
                     (release_id, Jsonb(data)))
        sync_cases(conn, release_id, data["items"])
        conn.execute("INSERT INTO revenue_serving.current_release(singleton,release_id) "
                     "VALUES (true,%s) ON CONFLICT(singleton) DO UPDATE "
                     "SET release_id=excluded.release_id", (release_id,))
    return str(release_id)


def current_release():
    with connect() as conn:
        return conn.execute("SELECT r.release_id,r.published_at,r.data "
                            "FROM revenue_serving.current_release c "
                            "JOIN revenue_serving.releases r USING(release_id)").fetchone()
