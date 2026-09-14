"""Transactional incident lifecycle and a database-local task-delivery simulator."""
import hashlib
import json

from psycopg.types.json import Jsonb

from revenue_pipeline.store import connect


def sync_cases(conn, release_id, items):
    """Called inside the publication transaction under its source locks."""
    previous = {row["case_id"]: row for row in conn.execute(
        "SELECT * FROM revenue_serving.cases FOR UPDATE"
    ).fetchall()}
    active = set()
    for item in items:
        case_id = hashlib.sha256(
            f'{item["opportunity_id"]}:{item["reason"]}'.encode()
        ).hexdigest()
        active.add(case_id)
        old = previous.get(case_id)
        transition = old is None or old["state"] == "resolved"
        generation = (old["generation"] if old else 0) + int(transition)
        conn.execute("INSERT INTO revenue_serving.cases "
                     "(case_id,opportunity_id,state,generation,release_id,evidence) "
                     "VALUES (%s,%s,'open',%s,%s,%s) ON CONFLICT(case_id) DO UPDATE SET "
                     "state='open',generation=excluded.generation,release_id=excluded.release_id,"
                     "evidence=excluded.evidence,updated_at=clock_timestamp()",
                     (case_id, item["opportunity_id"], generation, release_id, Jsonb(item)))
        if transition:
            enqueue(conn, case_id, generation, "open", release_id, item)
    for case_id, old in previous.items():
        if case_id not in active and old["state"] == "open":
            conn.execute("UPDATE revenue_serving.cases SET state='resolved',release_id=%s,"
                         "updated_at=clock_timestamp() WHERE case_id=%s", (release_id, case_id))
            enqueue(conn, case_id, old["generation"], "resolved", release_id, old["evidence"])


def enqueue(conn, case_id, generation, action, release_id, evidence):
    key = f"{case_id}:{generation}:{action}"
    payload = {"case_id": case_id, "generation": generation, "action": action,
               "release_id": str(release_id), "evidence": evidence,
               "destination": "local-simulator"}
    conn.execute("INSERT INTO revenue_serving.outbox(event_key,case_id,action,payload) "
                 "VALUES (%s,%s,%s,%s) ON CONFLICT(event_key) DO NOTHING",
                 (key, case_id, action, Jsonb(payload)))


def dispatch(limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Dispatch batch must be between 1 and 1000")
    with connect() as conn:
        rows = conn.execute("SELECT event_key,payload FROM revenue_serving.outbox "
                            "WHERE delivered_at IS NULL ORDER BY created_at,event_key "
                            "LIMIT %s FOR UPDATE SKIP LOCKED", (limit,)).fetchall()
        for row in rows:
            conn.execute("INSERT INTO revenue_serving.simulated_tasks(event_key,payload) "
                         "VALUES (%s,%s) ON CONFLICT(event_key) DO NOTHING",
                         (row["event_key"], Jsonb(row["payload"])))
            conn.execute("UPDATE revenue_serving.outbox SET delivered_at=clock_timestamp() "
                         "WHERE event_key=%s", (row["event_key"],))
    return len(rows)


if __name__ == "__main__":
    print(json.dumps({"delivered_to_local_simulator": dispatch()}))
