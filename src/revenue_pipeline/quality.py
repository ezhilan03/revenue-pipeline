"""Build and test frozen source data before atomically publishing a serving release."""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from revenue_pipeline.operations import track_job
from revenue_pipeline.publication import capture_release, publication_lock


def build(project: Path, execute=subprocess.run):
    parsed = urlparse(os.environ["DATABASE_URL"])
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
        raise ValueError("DATABASE_URL must be a PostgreSQL URL")
    env = dict(os.environ, PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432),
               PGUSER=unquote(parsed.username or ""), PGPASSWORD=unquote(parsed.password or ""),
               PGDATABASE=unquote(parsed.path.lstrip("/")))
    # Separate locked project venv avoids mixing Airflow and dbt dependency graphs.
    dbt = str(Path(sys.executable).parent / "dbt")
    with track_job("quality"), publication_lock() as conn:
        execute([dbt, "build", "--project-dir", str(project), "--profiles-dir", str(project)],
                env=env, check=True, timeout=600)
        return capture_release(conn)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path("dbt"))
    args = parser.parse_args()
    build(args.project_dir)


if __name__ == "__main__":
    main()
