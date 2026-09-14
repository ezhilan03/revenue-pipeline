"""One bounded poll per source; exit nonzero on failure for a future scheduler."""
import argparse
import json
import os
import time
import uuid

import httpx

from revenue_pipeline.archive import Archive
from revenue_pipeline.ingest import poll
from revenue_pipeline.operations import track_job


def run(base_url: str, client: httpx.Client, emit=print, archive=None):
    run_id = str(uuid.uuid4())
    counts = {}
    for source in ("crm", "contracts"):
        started = time.monotonic()
        try:
            with track_job(source):
                counts[source] = poll(
                    source, f"{base_url.rstrip('/')}/feeds/{source}", client,
                    archive=archive, emit_archive=lambda value: emit(json.dumps(value)),
                )
        except Exception as exc:
            # Never log DSNs, URLs, response bodies or credentials.
            emit(json.dumps({"run_id": run_id, "source": source, "status": "failed",
                             "error_type": type(exc).__name__,
                             "duration_seconds": round(time.monotonic() - started, 3)}))
            raise
        emit(json.dumps({"run_id": run_id, "source": source, "status": "succeeded",
                         "inserted": counts[source],
                         "duration_seconds": round(time.monotonic() - started, 3)}))
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default="http://127.0.0.1:8027")
    parser.add_argument("--archive-dir", default=os.environ.get("REVENUE_ARCHIVE_DIR", "reports/raw"))
    args = parser.parse_args()
    try:
        with httpx.Client() as client:
            run(args.source_url, client, archive=Archive(args.archive_dir))
    except Exception:  # noqa: BLE001 - CLI boundary must not expose secrets in tracebacks
        # Structured failure already emitted; suppress possibly sensitive traceback.
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
