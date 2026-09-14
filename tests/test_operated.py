import json

import httpx
import pytest
from fastapi.testclient import TestClient

from revenue_pipeline.ingest import poll
from revenue_pipeline.runner import run
from revenue_pipeline.simulator import create_app
from revenue_pipeline.store import checkpoint, connect


def test_http_runner_replay_and_delivery():
    logs = []
    with TestClient(create_app()) as client:
        assert run("http://testserver", client, logs.append) == {"crm": 1, "contracts": 0}
        assert run("http://testserver", client, logs.append) == {"crm": 0, "contracts": 0}
    with connect() as conn:
        assert len(conn.execute("SELECT * FROM revenue.closed_won_without_contract").fetchall()) == 1
    with TestClient(create_app(True)) as client:
        assert run("http://testserver", client, logs.append) == {"crm": 0, "contracts": 1}
    with connect() as conn:
        assert conn.execute("SELECT * FROM revenue.closed_won_without_contract").fetchall() == []
    assert all(json.loads(line)["status"] == "succeeded" for line in logs)


@pytest.mark.parametrize("query", ["cursor=-1", "limit=0", "limit=101"])
def test_feed_rejects_invalid_pagination(query):
    with TestClient(create_app()) as client:
        assert client.get(f"/feeds/crm?{query}").status_code == 422


def test_feed_restart_cannot_silently_rewind_consumer():
    with TestClient(create_app()) as client:
        assert client.get("/feeds/contracts?cursor=1").status_code == 409


def test_network_retry_is_bounded_and_does_not_advance():
    calls, delays = [], []

    def broken(request):
        calls.append(request)
        raise httpx.ConnectError("synthetic", request=request)

    with (httpx.Client(transport=httpx.MockTransport(broken)) as client,
          pytest.raises(httpx.ConnectError)):
        poll("crm", "http://source/feeds/crm", client, sleep=delays.append)
    assert len(calls) == 4
    assert delays == [1, 2, 4]
    assert checkpoint("crm") == 0


def test_transient_timeout_recovers():
    calls = []

    def transient(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("synthetic", request=request)
        return httpx.Response(200, json={"records": [], "next_cursor": 0, "has_more": False})

    with httpx.Client(transport=httpx.MockTransport(transient)) as client:
        assert poll("crm", "http://source", client, sleep=lambda _: None) == 0
    assert len(calls) == 2


def test_runner_failure_is_reported_without_sensitive_response():
    logs = []
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(401, text="secret-body")
    )) as client, pytest.raises(httpx.HTTPStatusError):
        run("http://source", client, logs.append)
    assert json.loads(logs[0])["status"] == "failed"
    assert "secret-body" not in logs[0]
    assert checkpoint("contracts") == 0
