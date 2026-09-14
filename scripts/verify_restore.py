"""Bounded local disaster-recovery smoke; never restores over an existing database."""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

TABLES = {
    "revenue_raw": ("events", "checkpoints", "job_runs"),
    "revenue_serving": ("releases", "current_release", "cases", "outbox", "simulated_tasks"),
}


def fingerprint(dsn):
    result = {}
    with psycopg.connect(dsn) as conn:
        for schema, tables in TABLES.items():
            for table in tables:
                rows = conn.execute(sql.SQL("SELECT to_jsonb(t)::text FROM {}.{} t").format(
                    sql.Identifier(schema), sql.Identifier(table))).fetchall()
                payload = "\n".join(sorted(row[0] for row in rows)).encode()
                result[f"{schema}.{table}"] = {
                    "rows": len(rows), "sha256": hashlib.sha256(payload).hexdigest(),
                }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", required=True)
    args = parser.parse_args()
    dsn = os.environ["REVENUE_TEST_DATABASE_URL"]
    parsed = urlparse(dsn)
    source = parsed.path.lstrip("/")
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not source.endswith("_test"):
        raise ValueError("Restore smoke requires a loopback disposable _test database")
    target = f"revenue_restore_{uuid4().hex[:12]}_test"
    output = Path("reports") / f"{target}.dump"
    output.parent.mkdir(exist_ok=True)
    before = fingerprint(dsn)
    started = time.monotonic()
    with output.open("xb") as stream:
        subprocess.run(["docker", "exec", args.container, "pg_dump", "-U", parsed.username,
                        "-d", source, "--format=custom", "--no-owner", "--no-acl"],
                       stdout=stream, check=True, timeout=120)
    if fingerprint(dsn) != before:
        raise RuntimeError("Source changed during dump; stop writers and retry")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    with output.open("rb") as stream:
        subprocess.run(["docker", "exec", "-i", args.container, "pg_restore", "-U", parsed.username,
                        "-d", target, "--no-owner", "--no-acl", "--exit-on-error"],
                       stdin=stream, check=True, timeout=120)
    restored = fingerprint(make_conninfo(dsn, dbname=target))
    if restored != before:
        raise RuntimeError("Restored table fingerprints differ; retained artifacts for inspection")
    print(json.dumps({"status": "passed", "target_database": target,
                      "backup_file": str(output), "elapsed_seconds": round(time.monotonic()-started, 3),
                      "tables": restored}, indent=2))


if __name__ == "__main__":
    main()
