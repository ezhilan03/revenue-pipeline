"""Real login verification in a new disposable database; never alters existing data."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import psycopg
from psycopg import errors, sql
from psycopg.rows import dict_row

from revenue_pipeline.database_roles import provision
from revenue_pipeline.demo import CONTRACT, CRM
from revenue_pipeline.outbox import dispatch
from revenue_pipeline.quality import build
from revenue_pipeline.store import checkpoint, ingest_page, initialize


@contextmanager
def live_api(dsn, key):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # The API process receives no owner/test DSN or sibling-profile passwords.
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "revenue_pipeline.api:app", "--host", "127.0.0.1",
         "--port", str(port), "--no-access-log"],
        env={"PATH": os.environ.get("PATH", ""), "DATABASE_URL": dsn, "REVENUE_API_KEY": key},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10,
                          headers={"X-API-Key": key}, trust_env=False) as client:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("API process exited during startup")
                try:
                    if client.get("/health/live").status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("API startup exceeded ten seconds")
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    source = os.environ["REVENUE_TEST_DATABASE_URL"]
    parsed = urlparse(source)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.endswith("_test"):
        raise ValueError("Identity verification requires a loopback disposable _test database")
    suffix = uuid4().hex[:12]
    database = f"revenue_identity_{suffix}_test"
    owner_url = parsed._replace(path=f"/{database}").geturl()
    logins = {}
    with psycopg.connect(source, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        os.environ["DATABASE_URL"] = owner_url
        initialize()
        with psycopg.connect(owner_url, row_factory=dict_row) as admin:
            groups = provision(admin, database)
            for profile, group in groups.items():
                login = f"rv_{suffix}_{profile}"
                password = secrets.token_urlsafe(32)
                admin.execute(sql.SQL("CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB "
                                      "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(
                    sql.Identifier(login), sql.Literal(password)))
                admin.execute(sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(group), sql.Identifier(login)))
                logins[profile] = (login, parsed._replace(
                    netloc=f"{login}:{password}@{parsed.hostname}:{parsed.port or 5432}",
                    path=f"/{database}").geturl())

        def use(profile):
            os.environ["DATABASE_URL"] = logins[profile][1]

        use("ingest")
        ingest_page("crm", [CRM], 0, 1)
        ingest_page("contracts", [], 0, 0)
        assert checkpoint("crm") == 1
        use("transform")
        first = build(Path("dbt"))  # Actual dbt subprocess authenticates as transform.
        use("dispatch")
        assert dispatch() == 1
        assert dispatch() == 0
        use("api")
        key = secrets.token_urlsafe(32)
        os.environ["REVENUE_API_KEY"] = key
        with live_api(logins["api"][1], key) as client:
            response = client.get("/exceptions")
            assert response.status_code == 200, response.status_code
            assert len(response.json()["items"]) == 1
            assert client.get("/metrics").status_code == 200
            assert client.get("/forecast").status_code == 200
            assert client.get("/exceptions", headers={"X-API-Key": "wrong"}).status_code == 401

            def read(_):
                start = time.monotonic()
                result = client.get("/exceptions")
                assert result.status_code == 200
                assert result.json()["release_id"] == first
                return (time.monotonic() - start) * 1000

            with ThreadPoolExecutor(max_workers=4) as pool:
                latencies = sorted(pool.map(read, range(40)))
        with psycopg.connect(logins["api"][1]) as conn:
            try:
                conn.execute("DELETE FROM revenue_serving.cases")
            except errors.InsufficientPrivilege:
                conn.rollback()
            else:
                raise AssertionError("API login could mutate cases")
        use("ingest")
        ingest_page("contracts", [CONTRACT], 0, 1)
        use("transform")
        second = build(Path("dbt"))
        assert first != second
        use("dispatch")
        assert dispatch() == 1
        use("api")
        with live_api(logins["api"][1], key) as client:
            response = client.get("/exceptions")
            assert response.status_code == 200
            assert response.json()["items"] == []
        print(json.dumps({"status": "passed", "database": database,
                          "authenticated_profiles": list(logins),
                          "http_probe": {"requests": 40, "concurrency": 4,
                                         "p95_ms": round(latencies[37], 3)},
                          "checks": ["ingestion", "dbt_and_publication", "idempotent_dispatch",
                                     "api_read_and_write_denial", "resolution"]}))
    finally:
        # Keep database evidence. Retire only identities created by this run;
        # generated passwords are never printed, committed or retained on disk.
        with psycopg.connect(source, autocommit=True) as admin:
            for login, _ in logins.values():
                if admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (login,)).fetchone():
                    admin.execute(sql.SQL("ALTER ROLE {} NOLOGIN PASSWORD NULL").format(
                        sql.Identifier(login)))
        os.environ["DATABASE_URL"] = source


if __name__ == "__main__":
    main()
