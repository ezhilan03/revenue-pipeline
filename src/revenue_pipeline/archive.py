"""Local content-addressed landing and replay. This is not cloud WORM storage."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from revenue_pipeline.contracts import Event
from revenue_pipeline.store import checkpoint, connect, ingest_page

MAX_BYTES = 8 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class Archive:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, value):
        content = canonical(value)
        if len(content) > MAX_BYTES:
            raise ValueError("Archive object exceeds 8 MiB local limit")
        digest = hashlib.sha256(content).hexdigest()
        target = self.root / f"{digest}.json"
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)  # publish without replacing an existing object
            except FileExistsError:
                if target.read_bytes() != content:
                    raise ValueError("Existing archive object is corrupt") from None
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return digest

    def get(self, digest):
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid archive digest")
        with (self.root / f"{digest}.json").open("rb") as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES or hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Archive checksum mismatch or size limit exceeded")
        return json.loads(content)

    def page(self, source, cursor, page):
        return self.put({"kind": "page-v1", "source": source, "cursor": cursor, "page": page})

    def manifest(self, source, pages):
        return self.put({"kind": "completed-poll-v1", "source": source, "pages": pages})


def validate_page(obj):
    if set(obj) != {"kind", "source", "cursor", "page"} or obj["kind"] != "page-v1":
        raise ValueError("Invalid archived page")
    source, cursor, page = obj["source"], obj["cursor"], obj["page"]
    if source not in {"crm", "contracts"} or type(cursor) is not int or cursor < 0:
        raise ValueError("Invalid source/cursor")
    if not isinstance(page, dict) or set(page) != {"records", "next_cursor", "has_more"}:
        raise ValueError("Invalid page envelope")
    if (not isinstance(page["records"], list) or type(page["next_cursor"]) is not int
            or type(page["has_more"]) is not bool
            or page["next_cursor"] != cursor + len(page["records"])
            or (page["has_more"] and not page["records"])):
        raise ValueError("Invalid archived pagination")
    if any(Event.model_validate(record).source != source for record in page["records"]):
        raise ValueError("Mixed archived source")
    return obj


def replay(archive, digest):
    obj = archive.get(digest)
    if obj.get("kind") == "completed-poll-v1":
        if set(obj) != {"kind", "source", "pages"} or not isinstance(obj["pages"], list):
            raise ValueError("Invalid manifest")
        if not 1 <= len(obj["pages"]) <= 1000:
            raise ValueError("Invalid manifest page count")
        pages = [validate_page(archive.get(item)) for item in obj["pages"]]
        for i, item in enumerate(pages):
            if item["source"] != obj["source"]:
                raise ValueError("Manifest source mismatch")
            if i and item["cursor"] != pages[i - 1]["page"]["next_cursor"]:
                raise ValueError("Manifest cursor gap")
            if item["page"]["has_more"] != (i < len(pages) - 1):
                raise ValueError("Manifest completion mismatch")
    else:
        pages = [validate_page(obj)]
    # Validate every checksum and contract before changing the database.
    inserted = 0
    for item in pages:
        source, cursor, page = item["source"], item["cursor"], item["page"]
        current = checkpoint(source)
        if current == cursor:
            inserted += ingest_page(source, page["records"], cursor, page["next_cursor"])
        elif current >= page["next_cursor"]:
            # Never trust the offset alone when replaying already committed pages.
            with connect() as conn:
                for record in page["records"]:
                    event = Event.model_validate(record)
                    row = conn.execute("SELECT payload_hash FROM revenue_raw.events "
                                       "WHERE source=%s AND entity_id=%s AND version=%s",
                                       (source, event.entity_id, event.version)).fetchone()
                    expected = hashlib.sha256(canonical(event.model_dump())).hexdigest()
                    if not row or row["payload_hash"] != expected:
                        raise ValueError("Committed data disagrees with archive")
        else:
            raise ValueError("Replay cursor gap or overlapping page")
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("digest")
    parser.add_argument("--archive-dir", required=True)
    args = parser.parse_args()
    print(json.dumps({"inserted": replay(Archive(args.archive_dir), args.digest)}))


if __name__ == "__main__":
    main()
