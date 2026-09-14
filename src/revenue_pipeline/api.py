import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response

from revenue_pipeline.operations import metrics
from revenue_pipeline.publication import current_release
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


@app.get("/metrics", dependencies=[Depends(authorize)])
def monitoring():
    return Response(metrics(), media_type="text/plain; version=0.0.4")


@app.get("/cases", dependencies=[Depends(authorize)])
def cases(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    with connect() as conn:
        items = conn.execute("SELECT * FROM revenue_serving.cases ORDER BY case_id "
                             "LIMIT %s OFFSET %s", (limit, offset)).fetchall()
    return {"items": items, "limit": limit, "offset": offset}


@app.get("/exceptions", dependencies=[Depends(authorize)])
def exceptions(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    release = serving_release()
    return {"items": release["data"]["items"][offset:offset + limit],
            "source_freshness": release["data"]["source_freshness"],
            "release_id": release["release_id"], "published_at": release["published_at"],
            "limit": limit, "offset": offset}


def serving_release():
    release = current_release()
    if release is None:
        raise HTTPException(503, "No validated release has been published")
    return release


@app.get("/opportunities/{opportunity_id}/history", dependencies=[Depends(authorize)])
def history(opportunity_id: str):
    release = serving_release()
    rows = [row for row in release["data"]["history"]
            if row["opportunity_id"] == opportunity_id]
    if not rows:
        raise HTTPException(404, "Opportunity not found")
    return {"items": rows, "release_id": release["release_id"],
            "published_at": release["published_at"]}
