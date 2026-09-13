import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from revenue_pipeline.store import connect

app = FastAPI(title="Revenue Handoff Reliability", version="0.1.0")


def authorize(x_api_key: Annotated[str | None, Header()] = None):
    expected = os.environ.get("REVENUE_API_KEY")
    if not expected:
        raise HTTPException(503, "API authentication not configured")
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid API key")


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/exceptions", dependencies=[Depends(authorize)])
def exceptions(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM revenue.closed_won_without_contract "
            "ORDER BY opportunity_id LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()
        freshness = conn.execute(
            "SELECT source,last_success_at, "
            "extract(epoch FROM clock_timestamp()-last_success_at)::float AS age_seconds "
            "FROM revenue_raw.checkpoints ORDER BY source"
        ).fetchall()
    return {"items": rows, "source_freshness": freshness, "limit": limit, "offset": offset}


@app.get("/opportunities/{opportunity_id}/history", dependencies=[Depends(authorize)])
def history(opportunity_id: str):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM revenue.opportunity_history WHERE opportunity_id=%s "
            "ORDER BY known_from", (opportunity_id,)
        ).fetchall()
    if not rows:
        raise HTTPException(404, "Opportunity not found")
    return {"items": rows}
