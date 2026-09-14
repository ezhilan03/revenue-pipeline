"""Local-only notification audit sink; no email, Slack or external recipient."""
import hashlib
import json
import os
import sqlite3
from typing import Literal

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from revenue_pipeline.api import authorize

app = FastAPI(title="Local alert delivery audit")


class Notification(BaseModel):
    status: Literal["firing", "resolved"]
    alerts: list[dict] = Field(min_length=1, max_length=100)
    groupKey: str = Field(max_length=2048)


def database():
    conn = sqlite3.connect(os.environ["ALERT_DATABASE_PATH"], timeout=5)
    conn.execute("CREATE TABLE IF NOT EXISTS notifications ("
                 "digest TEXT PRIMARY KEY, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                 "status TEXT NOT NULL, payload TEXT NOT NULL)")
    return conn


@app.post("/alerts", dependencies=[Depends(authorize)])
def receive(notification: Notification):
    payload = json.dumps(notification.model_dump(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    conn = database()
    try:
        with conn:
            conn.execute("INSERT OR IGNORE INTO notifications(digest,status,payload) VALUES (?,?,?)",
                         (digest, notification.status, payload))
    finally:
        conn.close()
    return {"accepted": True, "digest": digest}


@app.get("/notifications", dependencies=[Depends(authorize)])
def notifications():
    conn = database()
    try:
        rows = conn.execute("SELECT digest,received_at,status FROM notifications "
                            "ORDER BY received_at DESC,digest LIMIT 100").fetchall()
    finally:
        conn.close()
    return {"items": [dict(zip(("digest", "received_at", "status"), row, strict=True)) for row in rows]}
