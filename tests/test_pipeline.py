from concurrent.futures import ThreadPoolExecutor

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from revenue_pipeline.api import app
from revenue_pipeline.contracts import Event
from revenue_pipeline.demo import CONTRACT, CRM
from revenue_pipeline.ingest import poll
from revenue_pipeline.store import checkpoint, connect, ingest_page


def query(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def test_missing_contract_resolves_after_delivery():
    ingest_page("crm", [CRM], 0, 1)
    before = query("SELECT * FROM revenue.closed_won_without_contract")
    assert len(before) == 1
    assert before[0]["amount_minor"] == 1250000
    assert before[0]["currency"] == "GBP"
    ingest_page("contracts", [CONTRACT], 0, 1)
    assert query("SELECT * FROM revenue.closed_won_without_contract") == []


def test_duplicates_are_idempotent():
    assert ingest_page("crm", [CRM, CRM], 0, 2) == 1
    assert ingest_page("crm", [CRM], 2, 3) == 0
    assert len(query("SELECT * FROM revenue_raw.events")) == 1
    assert len(query("SELECT * FROM revenue.closed_won_without_contract")) == 1
    assert checkpoint("crm") == 3


def test_conflicting_version_rolls_back_entire_page():
    ingest_page("crm", [CRM], 0, 1)
    other = dict(CRM, entity_id="other", opportunity_id="other")
    with pytest.raises(ValueError, match="rewrote"):
        ingest_page("crm", [other, dict(CRM, amount_minor=1)], 1, 3)
    assert checkpoint("crm") == 1
    assert len(query("SELECT * FROM revenue_raw.events")) == 1


def test_invalid_page_does_not_advance_checkpoint():
    with pytest.raises(ValidationError):
        ingest_page("crm", [dict(CRM, amount_minor=12.34)], 0, 1)
    assert checkpoint("crm") == 0
    assert query("SELECT * FROM revenue_raw.events") == []


def test_late_correction_preserves_as_known_history():
    ingest_page("crm", [CRM], 0, 1)
    old = query("SELECT * FROM revenue.opportunity_history")[0]
    ingest_page("crm", [dict(CRM, version=3, amount_minor=900000)], 1, 2)
    ingest_page("crm", [dict(CRM, version=2, amount_minor=800000)], 2, 3)
    rows = query("SELECT * FROM revenue.opportunity_history ORDER BY known_from")
    assert [r["version"] for r in rows] == [1, 3]
    assert rows[0]["known_from"] == old["known_from"]
    assert rows[0]["amount_minor"] == old["amount_minor"]
    assert rows[0]["known_to"] == rows[1]["known_from"]
    assert rows[1]["known_to"] is None
    assert query("SELECT amount_minor FROM revenue.current_opportunities")[0]["amount_minor"] == 900000


def test_deleted_opportunity_does_not_resurrect():
    ingest_page("crm", [dict(CRM, version=3, deleted=True)], 0, 1)
    ingest_page("crm", [CRM], 1, 2)
    assert query("SELECT * FROM revenue.current_opportunities") == []


@pytest.mark.parametrize("change", [{"deleted": True}, {"status": "cancelled"}])
def test_contract_retraction_reopens_exception(change):
    ingest_page("crm", [CRM], 0, 1)
    ingest_page("contracts", [CONTRACT], 0, 1)
    ingest_page("contracts", [dict(CONTRACT, version=2, **change)], 1, 2)
    assert len(query("SELECT * FROM revenue.closed_won_without_contract")) == 1


def test_draft_or_unrelated_contract_does_not_hide_exception():
    ingest_page("crm", [CRM], 0, 1)
    ingest_page("contracts", [dict(CONTRACT, status="draft")], 0, 1)
    other = dict(CONTRACT, entity_id="other", opportunity_id="other")
    ingest_page("contracts", [other], 1, 2)
    assert len(query("SELECT * FROM revenue.closed_won_without_contract")) == 1


def test_concurrent_pollers_cannot_overwrite_progress():
    def attempt():
        try:
            ingest_page("crm", [CRM], 0, 1)
            return "committed"
        except ValueError:
            return "restart"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["committed", "restart"]
    assert len(query("SELECT * FROM revenue_raw.events")) == 1


def test_raw_event_update_is_rejected():
    ingest_page("crm", [CRM], 0, 1)
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        query("UPDATE revenue_raw.events SET version=2 RETURNING version")


def test_rate_limit_then_multiple_pages():
    requests = []
    sleeps = []
    def handler(request):
        cursor = int(request.url.params["cursor"])
        requests.append(cursor)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        record = CRM if cursor == 0 else dict(CRM, version=2)
        return httpx.Response(200, json={
            "records": [record], "next_cursor": cursor + 1, "has_more": cursor == 0,
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert poll("crm", "https://synthetic.invalid/events", client, sleep=sleeps.append) == 2
    assert requests == [0, 0, 1]
    assert sleeps == [1]
    assert checkpoint("crm") == 2


def test_exhausted_retry_leaves_progress_unchanged():
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        poll("crm", "https://synthetic.invalid/events", client, sleep=lambda _: None)
    assert checkpoint("crm") == 0


def test_bad_cursor_is_rejected():
    with pytest.raises(ValueError, match="Cursor"):
        ingest_page("crm", [CRM], 0, 10)


def test_api_requires_auth_and_returns_evidence():
    ingest_page("crm", [CRM], 0, 1)
    with TestClient(app) as client:
        assert client.get("/exceptions").status_code == 401
        response = client.get("/exceptions", headers={"X-API-Key": "local-test-key-not-for-deployment"})
        assert response.status_code == 200
        assert len(response.json()["items"][0]["crm_evidence_hash"]) == 64
        assert client.get("/exceptions?limit=101", headers={
            "X-API-Key": "local-test-key-not-for-deployment"
        }).status_code == 422


@pytest.mark.parametrize("changes", [
    {"effective_at": "2026-01-01T00:00:00"}, {"currency": "XYZ"},
    {"amount_minor": -1}, {"version": True}, {"extra": "ignored?"},
])
def test_strict_data_contract(changes):
    with pytest.raises(ValidationError):
        Event.model_validate(dict(CRM, **changes))
