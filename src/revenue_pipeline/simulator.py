"""Read-only synthetic offset feeds. Never expose this demo source publicly."""
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query

from revenue_pipeline.demo import CONTRACT, CRM


def create_app(deliver_contract: bool = False) -> FastAPI:
    app = FastAPI(title="Synthetic revenue sources")
    feeds = {"crm": [CRM], "contracts": [CONTRACT] if deliver_contract else []}

    @app.get("/health/live")
    def live():
        return {"status": "ok", "synthetic": True}

    @app.get("/feeds/{source}")
    def feed(source: Literal["crm", "contracts"], cursor: int = Query(0, ge=0),
             limit: int = Query(100, ge=1, le=100)):
        records = feeds[source]
        if cursor > len(records):
            raise HTTPException(409, "Cursor exceeds feed; do not reset consumer checkpoints")
        page = records[cursor:cursor + limit]
        next_cursor = cursor + len(page)
        return {"records": page, "next_cursor": next_cursor,
                "has_more": next_cursor < len(records)}

    return app


def from_environment():
    mode = os.environ.get("SIMULATOR_DELIVER_CONTRACT", "0")
    if mode not in {"0", "1"}:
        raise ValueError("SIMULATOR_DELIVER_CONTRACT must be 0 or 1")
    return create_app(mode == "1")
