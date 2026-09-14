"""Declared synthetic workload, isolated database; not a cloud SLA benchmark."""
import json
import os
import statistics
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from revenue_pipeline.api import app
from revenue_pipeline.demo import CONTRACT, CRM
from revenue_pipeline.quality import build
from revenue_pipeline.store import ingest_page, initialize


def main():
    original = os.environ["REVENUE_TEST_DATABASE_URL"]
    parsed = urlparse(original)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.endswith("_test"):
        raise ValueError("Benchmark requires a local disposable _test database")
    database = f"revenue_load_{uuid4().hex[:12]}_test"
    with psycopg.connect(original, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    # Preserve URL format for the quality subprocess's environment conversion.
    os.environ["DATABASE_URL"] = original.rsplit("/", 1)[0] + "/" + database
    os.environ["REVENUE_API_KEY"] = "local-benchmark-only"
    initialize()
    started = time.monotonic()
    opportunities = [dict(CRM, entity_id=f"load-{i:04d}", opportunity_id=f"load-{i:04d}")
                     for i in range(1000)]
    contracts = [dict(CONTRACT, entity_id=f"contract-{i:04d}", opportunity_id=f"load-{i:04d}")
                 for i in range(500)]
    for source, records in (("crm", opportunities), ("contracts", contracts)):
        for offset in range(0, len(records), 100):
            batch = records[offset:offset+100]
            ingest_page(source, batch, offset, offset+len(batch))
    ingestion = time.monotonic() - started
    started = time.monotonic()
    release = build(Path("dbt"))
    publication = time.monotonic() - started
    timings = []
    with TestClient(app) as client:
        for _ in range(50):
            started = time.monotonic()
            response = client.get("/exceptions?limit=100",
                                  headers={"X-API-Key": "local-benchmark-only"})
            timings.append((time.monotonic() - started) * 1000)
            assert response.status_code == 200 and len(response.json()["items"]) == 100
    with psycopg.connect(make_conninfo(original, dbname=database)) as conn:
        assert conn.execute("SELECT count(*) FROM revenue_serving.cases WHERE state='open'").fetchone()[0] == 500
    report = {"database": database, "source_events": 1500, "open_cases": 500,
              "ingestion_seconds": round(ingestion, 3), "publication_seconds": round(publication, 3),
              "api_testclient_requests": 50, "median_ms": round(statistics.median(timings), 3),
              "p95_ms": round(sorted(timings)[47], 3), "release_id": release,
              "limitations": "Single local process; TestClient excludes real network; no SLA claim"}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
