"""One-time, explicit privilege provisioning; never called by application startup."""

import argparse
import hashlib
import json

from psycopg import sql

PROFILES = ("ingest", "transform", "api", "dispatch")
MODELS = ("opportunity_history", "current_opportunities", "current_contracts",
          "closed_won_without_contract")


def provision(conn, expected_database):
    """Create isolated NOLOGIN capability roles. Caller controls commit/rollback.

    Refuse existing names rather than silently reusing roles with unknown grants.
    Dedicated login identities and deployment wiring are a separate operation.
    """
    database = conn.execute("SELECT current_database() AS name").fetchone()["name"]
    if database != expected_database:
        raise ValueError("Connected database does not match expected database")
    suffix = hashlib.sha256(database.encode()).hexdigest()[:12]
    roles = {profile: f"rp_{suffix}_{profile}" for profile in PROFILES}
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout = '5s'")
        conn.execute("SELECT pg_advisory_xact_lock(73000)")
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname = ANY(%s)",
                        (list(roles.values()),)).fetchone():
            raise ValueError("Capability role already exists; inspect grants instead of reprovisioning")
        for role in roles.values():
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB "
                                 "NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(
                                     sql.Identifier(role)))

        def grant(profile, privileges, kind, target):
            # All privileges/kinds/targets below are fixed, reviewed code constants.
            conn.execute(sql.SQL("GRANT {} ON {} {} TO {}").format(
                sql.SQL(privileges), sql.SQL(kind), sql.SQL(target),
                sql.Identifier(roles[profile])))

        for profile in ("ingest", "transform", "api"):
            grant(profile, "USAGE", "SCHEMA", "revenue_raw")
        for profile in ("transform", "api", "dispatch"):
            grant(profile, "USAGE", "SCHEMA", "revenue_serving")
        grant("ingest", "SELECT, INSERT", "TABLE", "revenue_raw.events")
        grant("ingest", "SELECT, INSERT, UPDATE", "TABLE", "revenue_raw.checkpoints")
        for profile in ("ingest", "transform"):
            grant(profile, "SELECT, INSERT", "TABLE", "revenue_raw.job_runs")
            grant(profile, "UPDATE (status, finished_at, error_type)", "TABLE",
                  "revenue_raw.job_runs")
        for table in ("events", "checkpoints"):
            grant("transform", "SELECT", "TABLE", f"revenue_raw.{table}")
        grant("transform", "SELECT, INSERT", "TABLE", "revenue_serving.releases")
        for table in ("current_release", "cases"):
            grant("transform", "SELECT, INSERT, UPDATE", "TABLE", f"revenue_serving.{table}")
        grant("transform", "SELECT, INSERT", "TABLE", "revenue_serving.outbox")
        grant("api", "SELECT", "TABLE", "revenue_raw.job_runs")
        for table in ("releases", "current_release", "cases"):
            grant("api", "SELECT", "TABLE", f"revenue_serving.{table}")
        grant("api", "SELECT (delivered_at)", "TABLE", "revenue_serving.outbox")
        grant("dispatch", "SELECT", "TABLE", "revenue_serving.outbox")
        grant("dispatch", "UPDATE (delivered_at)", "TABLE", "revenue_serving.outbox")
        grant("dispatch", "SELECT, INSERT", "TABLE", "revenue_serving.simulated_tasks")

        # dbt replaces its own views: give ownership only of the reviewed model schema.
        conn.execute("CREATE SCHEMA IF NOT EXISTS revenue")
        grant("transform", "USAGE, CREATE", "SCHEMA", "revenue")
        for model in MODELS:
            row = conn.execute("SELECT c.relkind FROM pg_class c JOIN pg_namespace n "
                               "ON n.oid=c.relnamespace WHERE n.nspname='revenue' "
                               "AND c.relname=%s", (model,)).fetchone()
            if row:
                if row["relkind"] != "v":
                    raise ValueError("Expected a dbt view; review model ownership manually")
                conn.execute(sql.SQL("ALTER VIEW revenue.{} OWNER TO {}").format(
                    sql.Identifier(model), sql.Identifier(roles["transform"])))
    return roles


def main():
    from revenue_pipeline.store import connect

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-database", required=True)
    args = parser.parse_args()
    with connect() as conn:
        roles = provision(conn, args.expected_database)
    print(json.dumps(roles, indent=2))


if __name__ == "__main__":
    main()
