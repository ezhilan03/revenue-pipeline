import time

import httpx

from revenue_pipeline.store import checkpoint, ingest_page


def poll(source: str, url: str, client: httpx.Client, sleep=time.sleep, max_pages=1000):
    """Poll an append-only simulator log. Offset protocol is NOT generic CRM CDC."""
    inserted = 0
    for _ in range(max_pages):
        cursor = checkpoint(source)
        for attempt in range(4):
            response = client.get(url, params={"cursor": cursor, "limit": 100}, timeout=15)
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt == 3:
                response.raise_for_status()
            delay = response.headers.get("Retry-After", str(2**attempt))
            try:
                delay = min(30, max(0, float(delay)))
            except ValueError:
                delay = 2**attempt
            sleep(delay)
        response.raise_for_status()
        page = response.json()
        if set(page) != {"records", "next_cursor", "has_more"}:
            raise ValueError("Invalid page envelope")
        if type(page["has_more"]) is not bool or type(page["next_cursor"]) is not int:
            raise ValueError("Invalid cursor metadata")
        if not isinstance(page["records"], list):
            raise TypeError("records must be a list")
        if page["has_more"] and not page["records"]:
            raise ValueError("Non-progressing pagination")
        inserted += ingest_page(source, page["records"], cursor, page["next_cursor"])
        if not page["has_more"]:
            return inserted
    raise RuntimeError("Page limit reached; next run can resume committed progress")
