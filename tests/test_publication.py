import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from revenue_pipeline.api import app
from revenue_pipeline.demo import CONTRACT, CRM
from revenue_pipeline.publication import current_release, publication_lock
from revenue_pipeline.quality import build
from revenue_pipeline.store import connect, ingest_page

HEADERS = {"X-API-Key": "local-test-key-not-for-deployment"}


def test_real_dbt_test_failure_does_not_publish(tmp_path):
    first = build(Path("dbt"))
    project = tmp_path / "dbt"
    shutil.copytree("dbt", project, ignore=shutil.ignore_patterns("target", "logs", "dbt_packages"))
    shutil.copyfile("tests/fixtures/reject_release.sql", project / "tests" / "reject_release.sql")
    with pytest.raises(subprocess.CalledProcessError):
        build(project)
    assert str(current_release()["release_id"]) == first


def test_api_without_release_fails_closed():
    ingest_page("crm", [CRM], 0, 1)
    with TestClient(app) as client:
        assert client.get("/exceptions", headers=HEADERS).status_code == 503
        assert client.get("/opportunities/demo-001/history", headers=HEADERS).status_code == 503


def test_real_build_publishes_and_raw_changes_stay_hidden_until_next_release():
    ingest_page("crm", [CRM], 0, 1)
    first = build(Path("dbt"))
    ingest_page("contracts", [CONTRACT], 0, 1)
    with TestClient(app) as client:
        old = client.get("/exceptions", headers=HEADERS).json()
        assert old["release_id"] == first
        assert len(old["items"]) == 1
        second = build(Path("dbt"))
        new = client.get("/exceptions", headers=HEADERS).json()
        assert new["release_id"] == second != first
        assert new["items"] == []
        history = client.get("/opportunities/demo-001/history", headers=HEADERS).json()
        assert history["release_id"] == second
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM revenue_serving.releases").fetchone()["n"] == 2


def test_validation_failure_retains_previous_release_and_releases_locks():
    first = build(Path("dbt"), execute=lambda *a, **kw: None)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "dbt")

    with pytest.raises(subprocess.CalledProcessError):
        build(Path("dbt"), execute=fail)
    assert str(current_release()["release_id"]) == first
    with connect() as conn:
        assert conn.execute("SELECT pg_try_advisory_xact_lock(73001) AS ok").fetchone()["ok"]
        assert conn.execute("SELECT pg_try_advisory_xact_lock(73002) AS ok").fetchone()["ok"]


def test_publication_excludes_source_writes_and_other_publishers():
    with publication_lock(), connect() as other:
        assert not other.execute("SELECT pg_try_advisory_xact_lock(73001) AS ok").fetchone()["ok"]
        assert not other.execute("SELECT pg_try_advisory_xact_lock(73002) AS ok").fetchone()["ok"]


def test_release_rows_cannot_be_mutated():
    build(Path("dbt"), execute=lambda *a, **kw: None)
    with pytest.raises(psycopg.errors.RaiseException), connect() as conn:
        conn.execute("UPDATE revenue_serving.releases SET data='{}'::jsonb")


def test_pointer_failure_rolls_back_new_release():
    first = build(Path("dbt"), execute=lambda *a, **kw: None)
    with connect() as conn:
        conn.execute("CREATE OR REPLACE FUNCTION revenue_serving.test_reject_pointer() "
                     "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                     "RAISE EXCEPTION 'synthetic pointer failure'; END; $$")
        conn.execute("CREATE TRIGGER test_reject_pointer BEFORE UPDATE "
                     "ON revenue_serving.current_release FOR EACH ROW "
                     "EXECUTE FUNCTION revenue_serving.test_reject_pointer()")
    try:
        with pytest.raises(psycopg.errors.RaiseException):
            build(Path("dbt"), execute=lambda *a, **kw: None)
        assert str(current_release()["release_id"]) == first
        with connect() as conn:
            assert conn.execute("SELECT count(*) AS n FROM revenue_serving.releases").fetchone()["n"] == 1
    finally:
        with connect() as conn:
            conn.execute("DROP TRIGGER test_reject_pointer ON revenue_serving.current_release")
            conn.execute("DROP FUNCTION revenue_serving.test_reject_pointer()")
