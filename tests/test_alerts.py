from fastapi.testclient import TestClient

from revenue_pipeline.alert_receiver import app


def test_authenticated_durable_deduplicated_delivery(tmp_path, monkeypatch):
    monkeypatch.setenv("ALERT_DATABASE_PATH", str(tmp_path / "audit.sqlite"))
    headers = {"X-API-Key": "local-test-key-not-for-deployment"}
    payload = {"status": "firing", "alerts": [{"fingerprint": "synthetic"}], "groupKey": "test"}
    with TestClient(app) as client:
        assert client.post("/alerts", json=payload).status_code == 401
        assert client.post("/alerts", json=payload, headers=headers).status_code == 200
        client.post("/alerts", json=payload, headers=headers)
        client.post("/alerts", json=dict(payload, status="resolved"), headers=headers)
    with TestClient(app) as client:
        rows = client.get("/notifications", headers=headers).json()["items"]
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {"firing", "resolved"}
