from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest

from revenue_pipeline.demo import CONTRACT, CRM
from revenue_pipeline.outbox import dispatch
from revenue_pipeline.quality import build
from revenue_pipeline.store import connect, ingest_page


def publish():
    return build(Path("dbt"), execute=lambda *a, **kw: None)


def rows(table):
    # Only constant test table names are passed here.
    from psycopg import sql
    with connect() as conn:
        return conn.execute(sql.SQL("SELECT * FROM revenue_serving.{}").format(
            sql.Identifier(table))).fetchall()


def test_open_resolve_reopen_and_repeat_publication():
    ingest_page("crm", [CRM], 0, 1)
    publish()
    publish()
    assert len(rows("outbox")) == 1
    ingest_page("contracts", [CONTRACT], 0, 1)
    publish()
    assert rows("cases")[0]["state"] == "resolved"
    ingest_page("contracts", [dict(CONTRACT, version=2, status="cancelled")], 1, 2)
    publish()
    assert rows("cases")[0]["generation"] == 2
    assert len(rows("outbox")) == 3
    assert dispatch() == 3
    assert dispatch() == 0
    assert len(rows("simulated_tasks")) == 3


def test_concurrent_dispatch_is_idempotent():
    ingest_page("crm", [CRM], 0, 1)
    publish()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: dispatch(), range(2))) == 1
    assert len(rows("simulated_tasks")) == 1


def test_sink_failure_leaves_event_pending():
    ingest_page("crm", [CRM], 0, 1)
    publish()
    with connect() as conn:
        conn.execute("CREATE TRIGGER reject_simulated_task BEFORE INSERT ON "
                     "revenue_serving.simulated_tasks FOR EACH ROW "
                     "EXECUTE FUNCTION revenue_raw.reject_event_mutation()")
    try:
        with pytest.raises(psycopg.errors.RaiseException):
            dispatch()
        assert rows("outbox")[0]["delivered_at"] is None
        assert rows("simulated_tasks") == []
    finally:
        with connect() as conn:
            conn.execute("DROP TRIGGER reject_simulated_task ON revenue_serving.simulated_tasks")
    assert dispatch() == 1
