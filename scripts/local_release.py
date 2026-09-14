"""Opt-in local release with dedicated logins; never overwrites an existing database."""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from revenue_pipeline.database_roles import provision
from revenue_pipeline.store import initialize


def initialize_release():
    admin_url = os.environ["REVENUE_TEST_DATABASE_URL"]
    parsed = urlparse(admin_url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.endswith("_test"):
        raise ValueError("Use the loopback disposable test server as provisioning connection")
    suffix = uuid4().hex[:12]
    database = f"revenue_release_{suffix}"
    root = Path(".runtime")
    if root.is_symlink():
        raise ValueError("Runtime directory cannot be a symlink")
    root.mkdir(mode=0o700, exist_ok=True)
    path = root / suffix
    path.mkdir(mode=0o700)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    owner_url = parsed._replace(path=f"/{database}").geturl()
    os.environ["DATABASE_URL"] = owner_url
    initialize()
    config = {"database": database, "api_key": secrets.token_urlsafe(32), "profiles": {}}
    # Save credentials before commit: failed commits leave an unusable, private
    # config rather than orphaned active logins whose passwords were lost.
    with psycopg.connect(owner_url, row_factory=dict_row) as conn:
        roles = provision(conn, database)
        for profile, role in roles.items():
            name = f"release_{suffix}_{profile}"
            password = secrets.token_urlsafe(32)
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB "
                                 "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(password)))
            conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(role), sql.Identifier(name)))
            config["profiles"][profile] = parsed._replace(
                netloc=f"{name}:{password}@{parsed.hostname}:{parsed.port or 5432}",
                path=f"/{database}").geturl()
        fd = os.open(path / "credentials.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(config, stream)
            stream.flush()
            os.fsync(stream.fileno())
    print(json.dumps({"runtime": str(path), "database": database,
                      "note": "Credentials saved locally; never commit or share .runtime"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "seed", "publish", "dispatch", "api", "triage",
                                           "status"])
    parser.add_argument("--runtime", type=Path)
    args = parser.parse_args()
    if args.action == "init":
        initialize_release()
        return
    if args.runtime is None:
        parser.error("--runtime is required after init")
    credential_file = args.runtime / "credentials.json"
    if credential_file.is_symlink() or credential_file.stat().st_mode & 0o077:
        raise ValueError("Credentials must be a private regular file (mode 0600)")
    config = json.loads(credential_file.read_text())
    profile = {"seed": "ingest", "publish": "transform", "dispatch": "dispatch",
               "api": "api", "triage": "api", "status": "api"}[args.action]
    env = {"PATH": os.environ.get("PATH", ""), "DATABASE_URL": config["profiles"][profile],
           "REVENUE_API_KEY": config["api_key"]}
    if args.action == "status":
        import httpx

        with httpx.Client(base_url="http://127.0.0.1:8028", timeout=10, trust_env=False,
                          headers={"X-API-Key": config["api_key"]}) as client:
            incident = client.get("/exceptions")
            incident.raise_for_status()
            result = client.get("/forecast")
            result.raise_for_status()
            print(json.dumps({"status": "healthy", "incident_count": len(incident.json()["items"]),
                              "forecast": result.json()}, indent=2))
        return
    if args.action == "seed":
        # Synthetic first slice only; do not call demo.initialize() as a runtime login.
        from revenue_pipeline.demo import CRM
        from revenue_pipeline.store import checkpoint, ingest_page

        os.environ.clear()
        os.environ.update(env)
        c = checkpoint("crm")
        opened = {**CRM, "entity_id": "open-demo", "opportunity_id": "open-demo",
                  "stage": "open", "amount_minor": 500000}
        ingest_page("crm", [CRM, opened], c, c + 2)
        c = checkpoint("contracts")
        ingest_page("contracts", [], c, c)
        print("Synthetic incident seeded")
        return
    commands = {
        "publish": ["-m", "revenue_pipeline.quality", "--project-dir", "dbt"],
        "dispatch": ["-m", "revenue_pipeline.outbox"],
        "api": ["-m", "uvicorn", "revenue_pipeline.api:app", "--host", "127.0.0.1",
                "--port", "8028", "--no-access-log"],
        "triage": ["-m", "revenue_pipeline.triage", "--opportunity-id", "demo-001",
                   "--local-model", "qwen3:4b"],
    }
    # Only the selected login reaches the service; no owner or sibling credentials.
    os.execve(sys.executable, [sys.executable, *commands[args.action]], env)


if __name__ == "__main__":
    main()
