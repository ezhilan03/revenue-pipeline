import hashlib
import json
import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from revenue_pipeline.contracts import Event


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def initialize():
    """Development bootstrap; production role separation/migrations are a release gate."""
    with connect() as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS revenue_raw")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revenue_raw.events (
                source text NOT NULL CHECK (source IN ('crm', 'contracts')),
                entity_id text NOT NULL,
                version bigint NOT NULL CHECK (version > 0),
                payload jsonb NOT NULL,
                payload_hash text NOT NULL,
                observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                PRIMARY KEY (source, entity_id, version)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revenue_raw.checkpoints (
                source text PRIMARY KEY,
                cursor bigint NOT NULL DEFAULT 0 CHECK (cursor >= 0),
                last_success_at timestamptz NOT NULL DEFAULT clock_timestamp()
            )
        """)
        conn.execute("""
            CREATE OR REPLACE FUNCTION revenue_raw.reject_event_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Raw events are append-only'; END; $$
        """)
        conn.execute("DROP TRIGGER IF EXISTS immutable_event ON revenue_raw.events")
        conn.execute("""
            CREATE TRIGGER immutable_event BEFORE UPDATE OR DELETE ON revenue_raw.events
            FOR EACH ROW EXECUTE FUNCTION revenue_raw.reject_event_mutation()
        """)


def checkpoint(source: str) -> int:
    if source not in {"crm", "contracts"}:
        raise ValueError("Unsupported source")
    with connect() as conn:
        row = conn.execute(
            "SELECT cursor FROM revenue_raw.checkpoints WHERE source = %s", (source,)
        ).fetchone()
        return row["cursor"] if row else 0


def ingest_page(source: str, records: list[dict], expected_cursor: int, next_cursor: int):
    """All records and the checkpoint commit together. Conflicting replays fail closed."""
    if source not in {"crm", "contracts"}:
        raise ValueError("Unsupported source")
    if expected_cursor < 0 or next_cursor != expected_cursor + len(records):
        raise ValueError("Cursor must advance by exactly the source page length")
    events = [Event.model_validate(record) for record in records]
    if any(event.source != source for event in events):
        raise ValueError("Mixed source page")
    inserted = 0
    with connect() as conn:
        # Serialize checkpoint changes from concurrent runs of the same source.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (73001 if source == "crm" else 73002,))
        row = conn.execute(
            "SELECT cursor FROM revenue_raw.checkpoints WHERE source = %s", (source,)
        ).fetchone()
        if (row["cursor"] if row else 0) != expected_cursor:
            raise ValueError("Checkpoint changed; restart from persisted cursor")
        for event in events:
            payload = event.model_dump()
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            key = (source, event.entity_id, event.version)
            old = conn.execute(
                "SELECT payload_hash FROM revenue_raw.events "
                "WHERE source=%s AND entity_id=%s AND version=%s", key
            ).fetchone()
            if old:
                if old["payload_hash"] != digest:
                    raise ValueError("Source rewrote an existing version")
                continue
            conn.execute(
                "INSERT INTO revenue_raw.events "
                "(source, entity_id, version, payload, payload_hash) VALUES (%s,%s,%s,%s,%s)",
                (*key, Jsonb(payload), digest),
            )
            inserted += 1
        conn.execute(
            "INSERT INTO revenue_raw.checkpoints(source,cursor) VALUES (%s,%s) "
            "ON CONFLICT(source) DO UPDATE SET cursor=excluded.cursor, "
            "last_success_at=clock_timestamp()", (source, next_cursor)
        )
    return inserted
