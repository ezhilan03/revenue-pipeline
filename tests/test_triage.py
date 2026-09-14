import json

import httpx
import pytest

from revenue_pipeline.triage import suggest

ITEM = {"opportunity_id": "demo-001", "currency": "GBP", "amount_minor": 1250000,
        "reason": "closed_won_without_signed_contract", "crm_evidence_hash": "a" * 64}


def test_disabled_is_explicit_and_does_not_call_model():
    result = suggest(ITEM, "release")
    assert result["status"] == "disabled"
    assert result["facts"] == ITEM


def test_valid_model_selection_preserves_facts():
    response = {"next_check": "verify_crm_stage", "evidence_hash": "a" * 64}
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, json={"done": True, "response": json.dumps(response)}))) as client:
        result = suggest(ITEM, "release", "local", client)
    assert result["status"] == "validated_local_model"
    assert result["suggestion"] == response
    assert result["facts"] == ITEM


@pytest.mark.parametrize("response", [
    {"next_check": "pay_invoice", "evidence_hash": "a" * 64},
    {"next_check": "verify_contract_record", "evidence_hash": "b" * 64},
    {"next_check": "verify_contract_record", "evidence_hash": "a" * 64, "amount_minor": 0},
    "not an object", None,
])
def test_invalid_outputs_fall_back(response):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, json={"done": True, "response": json.dumps(response)}))) as client:
        result = suggest(ITEM, "release", "local", client)
    assert result["status"] == "fallback_invalid_or_unavailable_model"
    assert result["suggestion"]["next_check"] == "verify_contract_record"
    assert result["facts"] == ITEM


def test_model_failure_falls_back():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        assert suggest(ITEM, "release", "local", client)["status"].startswith("fallback")


def test_oversize_response_falls_back():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, content=b"x" * 65537))) as client:
        assert suggest(ITEM, "release", "local", client)["status"].startswith("fallback")
