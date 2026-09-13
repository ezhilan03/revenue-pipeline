import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

from revenue_pipeline.store import connect, initialize


@pytest.fixture(scope="session", autouse=True)
def warehouse():
    dsn = os.environ.get("REVENUE_TEST_DATABASE_URL")
    if not dsn or not urlparse(dsn).path.endswith("_test"):
        pytest.fail("Set REVENUE_TEST_DATABASE_URL to an isolated database ending _test")
    os.environ["DATABASE_URL"] = dsn
    os.environ["REVENUE_API_KEY"] = "local-test-key-not-for-deployment"
    parsed = urlparse(dsn)
    os.environ.update(
        PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432),
        PGUSER=parsed.username, PGPASSWORD=parsed.password, PGDATABASE=parsed.path[1:],
    )
    initialize()
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [str(root / ".venv/bin/dbt"), "run", "--project-dir", str(root / "dbt"),
         "--profiles-dir", str(root / "dbt")], check=True, capture_output=True, text=True,
    )


@pytest.fixture(autouse=True)
def clean_source_tables(warehouse):
    with connect() as conn:
        conn.execute("TRUNCATE revenue_raw.events, revenue_raw.checkpoints")
