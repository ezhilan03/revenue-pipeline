"""Incremental operational polling; logical dates do not time-travel the source."""
from datetime import UTC, datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

with DAG(
    dag_id="revenue_hourly",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    schedule="@hourly",
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=30),
    default_args={"retries": 2, "retry_delay": timedelta(seconds=30),
                  "execution_timeout": timedelta(minutes=12)},
    tags=["synthetic", "revenue", "local"],
) as dag:
    ingest = BashOperator(
        task_id="poll_sources",
        bash_command='/opt/revenue/.venv/bin/python -m revenue_pipeline.runner '
                     '--source-url "$REVENUE_SOURCE_URL"',
    )
    quality = BashOperator(
        task_id="dbt_quality_gate",
        bash_command='/opt/revenue/.venv/bin/python -m revenue_pipeline.quality '
                     '--project-dir /opt/revenue/dbt',
    )
    dispatch = BashOperator(
        task_id="dispatch_simulated_tasks",
        bash_command='/opt/revenue/.venv/bin/python -m revenue_pipeline.outbox',
    )
    ingest >> quality >> dispatch
