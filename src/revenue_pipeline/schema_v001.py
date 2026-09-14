"""Immutable baseline migration. Add future changes in a new migration file."""


def apply(conn):
    conn.execute("CREATE SCHEMA IF NOT EXISTS revenue_raw")
    conn.execute("CREATE SCHEMA IF NOT EXISTS revenue_serving")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revenue_serving.cases (
            case_id text PRIMARY KEY,
            opportunity_id text NOT NULL,
            state text NOT NULL CHECK(state IN ('open','resolved')),
            generation integer NOT NULL,
            release_id uuid NOT NULL,
            evidence jsonb NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revenue_serving.outbox (
            event_key text PRIMARY KEY,
            case_id text NOT NULL REFERENCES revenue_serving.cases(case_id),
            action text NOT NULL CHECK(action IN ('open','resolved')),
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            delivered_at timestamptz
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revenue_serving.simulated_tasks (
            event_key text PRIMARY KEY,
            payload jsonb NOT NULL,
            accepted_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revenue_serving.releases (
            release_id uuid PRIMARY KEY,
            published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            data jsonb NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revenue_serving.current_release (
            singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
            release_id uuid NOT NULL REFERENCES revenue_serving.releases(release_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revenue_raw.job_runs (
            run_id uuid PRIMARY KEY,
            job text NOT NULL CHECK (job IN ('crm', 'contracts', 'quality')),
            status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            finished_at timestamptz,
            error_type text
        )
    """)
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
    conn.execute("DROP TRIGGER IF EXISTS immutable_release ON revenue_serving.releases")
    conn.execute("""
        CREATE TRIGGER immutable_release BEFORE UPDATE OR DELETE ON revenue_serving.releases
        FOR EACH ROW EXECUTE FUNCTION revenue_raw.reject_event_mutation()
    """)
    conn.execute("""
        CREATE TRIGGER immutable_event BEFORE UPDATE OR DELETE ON revenue_raw.events
        FOR EACH ROW EXECUTE FUNCTION revenue_raw.reject_event_mutation()
    """)


