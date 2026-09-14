"""Durable job outcomes: page commits are not evidence of a completed source poll."""
from contextlib import contextmanager
from uuid import uuid4

from revenue_pipeline.store import connect


@contextmanager
def track_job(job):
    run_id = uuid4()
    with connect() as conn:
        conn.execute("INSERT INTO revenue_raw.job_runs(run_id,job,status) VALUES (%s,%s,'running')",
                     (run_id, job))
    try:
        yield run_id
    except Exception as exc:
        with connect() as conn:
            conn.execute("UPDATE revenue_raw.job_runs SET status='failed', "
                         "finished_at=clock_timestamp(),error_type=%s WHERE run_id=%s",
                         (type(exc).__name__, run_id))
        raise
    else:
        with connect() as conn:
            conn.execute("UPDATE revenue_raw.job_runs SET status='succeeded', "
                         "finished_at=clock_timestamp() WHERE run_id=%s", (run_id,))


def job_health():
    with connect() as conn:
        return conn.execute("""
            SELECT jobs.job, latest.status,
                extract(epoch FROM latest.started_at)::float AS started_timestamp,
                extract(epoch FROM successes.finished_at)::float AS success_timestamp
            FROM (VALUES ('crm'), ('contracts'), ('quality')) AS jobs(job)
            LEFT JOIN LATERAL (
                SELECT status,started_at FROM revenue_raw.job_runs r WHERE r.job=jobs.job
                ORDER BY started_at DESC,run_id DESC LIMIT 1
            ) latest ON true
            LEFT JOIN LATERAL (
                SELECT max(finished_at) AS finished_at FROM revenue_raw.job_runs r
                WHERE r.job=jobs.job AND status='succeeded'
            ) successes ON true ORDER BY jobs.job
        """).fetchall()


def metrics():
    lines = [
        '# HELP revenue_job_success Latest attempt succeeded; missing or running is zero.',
        '# TYPE revenue_job_success gauge',
        '# HELP revenue_job_last_success_timestamp_seconds Last full success, zero if absent.',
        '# TYPE revenue_job_last_success_timestamp_seconds gauge',
        '# HELP revenue_job_running Latest attempt remains running.',
        '# TYPE revenue_job_running gauge',
    ]
    for row in job_health():
        label = f'{{job="{row["job"]}"}}'
        lines.extend([
            f'revenue_job_success{label} {int(row["status"] == "succeeded")}',
            f'revenue_job_last_success_timestamp_seconds{label} {row["success_timestamp"] or 0}',
            f'revenue_job_running{label} {int(row["status"] == "running")}',
        ])
    with connect() as conn:
        backlog = conn.execute("SELECT count(*) AS n FROM revenue_serving.outbox "
                               "WHERE delivered_at IS NULL").fetchone()["n"]
        opened = conn.execute("SELECT count(*) AS n FROM revenue_serving.cases "
                              "WHERE state='open'").fetchone()["n"]
    lines.extend(['# TYPE revenue_outbox_pending gauge', f'revenue_outbox_pending {backlog}',
                  '# TYPE revenue_cases_open gauge', f'revenue_cases_open {opened}'])
    return '\n'.join(lines) + '\n'
