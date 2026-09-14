import subprocess
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from revenue_pipeline.api import app
from revenue_pipeline.demo import CRM
from revenue_pipeline.operations import job_health, metrics, track_job
from revenue_pipeline.quality import build
from revenue_pipeline.runner import run
from revenue_pipeline.store import checkpoint


def test_absent_jobs_are_not_healthy():
    assert all(row["status"] is None for row in job_health())
    assert 'revenue_job_success{job="crm"} 0' in metrics()
    assert 'revenue_job_last_success_timestamp_seconds{job="quality"} 0' in metrics()


def test_failed_attempt_retains_previous_success_time():
    with track_job("crm"):
        pass
    before = next(row for row in job_health() if row["job"] == "crm")
    with pytest.raises(ValueError), track_job("crm"):
        raise ValueError("synthetic")
    after = next(row for row in job_health() if row["job"] == "crm")
    assert after["status"] == "failed"
    assert after["success_timestamp"] == before["success_timestamp"]
    assert 'revenue_job_success{job="crm"} 0' in metrics()


def test_inflight_job_is_not_reported_as_success():
    with track_job("contracts"):
        assert 'revenue_job_running{job="contracts"} 1' in metrics()
        assert 'revenue_job_success{job="contracts"} 0' in metrics()
    assert 'revenue_job_running{job="contracts"} 0' in metrics()


def test_partial_source_commit_is_not_full_success():
    def pages(request):
        if request.url.params["cursor"] == "0":
            return httpx.Response(200, json={"records": [CRM], "next_cursor": 1,
                                            "has_more": True})
        return httpx.Response(200, json={"invalid": "envelope"})

    with httpx.Client(transport=httpx.MockTransport(pages)) as client, pytest.raises(ValueError):
        run("http://source", client, emit=lambda _: None)
    assert checkpoint("crm") == 1
    crm = next(row for row in job_health() if row["job"] == "crm")
    assert crm["status"] == "failed"
    assert crm["success_timestamp"] is None


def test_quality_failure_propagates_and_records_failure():
    def fail(command, **kwargs):
        assert "build" in command
        assert kwargs["check"] is True
        assert kwargs["timeout"] == 600
        raise subprocess.CalledProcessError(1, command)

    with pytest.raises(subprocess.CalledProcessError):
        build(Path("dbt"), execute=fail)
    quality = next(row for row in job_health() if row["job"] == "quality")
    assert quality["status"] == "failed"
    assert quality["success_timestamp"] is None


def test_quality_success_uses_database_url(monkeypatch):
    monkeypatch.setenv("PGDATABASE", "must-not-use-stale-database")

    def success(command, **kwargs):
        assert kwargs["env"]["PGDATABASE"].endswith("_test")

    build(Path("dbt"), execute=success)
    assert next(row for row in job_health() if row["job"] == "quality")["status"] == "succeeded"


def test_metrics_are_authenticated_and_prometheus_formatted():
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 401
        response = client.get("/metrics", headers={"X-API-Key": "local-test-key-not-for-deployment"})
    assert response.status_code == 200
    assert "version=0.0.4" in response.headers["content-type"]
    assert response.text.endswith("\n")
    assert 'revenue_job_success{job="contracts"} 0' in response.text
