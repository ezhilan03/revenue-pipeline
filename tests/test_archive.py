import json

import httpx
import pytest

from revenue_pipeline.archive import Archive, replay
from revenue_pipeline.demo import CRM
from revenue_pipeline.ingest import poll
from revenue_pipeline.store import checkpoint, connect, ingest_page


def page(records, next_cursor, more=False):
    return {"records": records, "next_cursor": next_cursor, "has_more": more}


def test_recover_object_archived_before_database_commit(tmp_path):
    archive = Archive(tmp_path)
    digest = archive.page("crm", 0, page([CRM], 1))
    assert checkpoint("crm") == 0
    assert replay(archive, digest) == 1
    assert replay(archive, digest) == 0
    assert checkpoint("crm") == 1


def test_manifest_replay_resumes_committed_prefix(tmp_path):
    archive = Archive(tmp_path)
    second = dict(CRM, version=2, amount_minor=20)
    one = archive.page("crm", 0, page([CRM], 1, True))
    two = archive.page("crm", 1, page([second], 2))
    manifest = archive.manifest("crm", [one, two])
    ingest_page("crm", [CRM], 0, 1)
    assert replay(archive, manifest) == 1
    assert replay(archive, manifest) == 0
    assert checkpoint("crm") == 2


def test_corrupt_object_fails_before_any_manifest_page_commits(tmp_path):
    archive = Archive(tmp_path)
    one = archive.page("crm", 0, page([CRM], 1, True))
    two = archive.page("crm", 1, page([dict(CRM, version=2)], 2))
    manifest = archive.manifest("crm", [one, two])
    (tmp_path / f"{two}.json").write_text("corruption")
    with pytest.raises(ValueError, match="checksum"):
        replay(archive, manifest)
    assert checkpoint("crm") == 0


def test_conflicting_existing_archive_is_not_overwritten(tmp_path):
    archive = Archive(tmp_path)
    digest = archive.page("crm", 0, page([CRM], 1))
    (tmp_path / f"{digest}.json").write_text("corruption")
    with pytest.raises(ValueError, match="corrupt"):
        archive.page("crm", 0, page([CRM], 1))
    assert (tmp_path / f"{digest}.json").read_text() == "corruption"


def test_checkpoint_alone_is_not_replay_proof(tmp_path):
    archive = Archive(tmp_path)
    digest = archive.page("crm", 0, page([CRM], 1))
    ingest_page("crm", [dict(CRM, amount_minor=7)], 0, 1)
    with pytest.raises(ValueError, match="disagrees"):
        replay(archive, digest)


@pytest.mark.parametrize("digest", ["../secret", "a" * 63, "/tmp/test"])
def test_digest_cannot_be_a_path(tmp_path, digest):
    with pytest.raises(ValueError, match="digest"):
        Archive(tmp_path).get(digest)


def test_incomplete_manifest_rejected(tmp_path):
    archive = Archive(tmp_path)
    item = archive.page("crm", 0, page([CRM], 1, True))
    with pytest.raises(ValueError, match="completion"):
        replay(archive, archive.manifest("crm", [item]))
    assert checkpoint("crm") == 0


def test_poll_archives_invalid_records_without_completion_manifest(tmp_path):
    archive = Archive(tmp_path)
    logs = []
    response = page([dict(CRM, amount_minor=1.25)], 1)
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=response)
    )) as client, pytest.raises(ValueError):
        poll("crm", "http://source", client, archive=archive, emit_archive=logs.append)
    assert len(logs) == 1 and "archive_page" in logs[0]
    assert archive.get(logs[0]["archive_page"])["page"] == response
    assert checkpoint("crm") == 0


def test_archive_failure_prevents_checkpoint_commit(tmp_path, monkeypatch):
    archive = Archive(tmp_path)

    def fail(*args):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(archive, "page", fail)
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=page([CRM], 1))
    )) as client, pytest.raises(OSError):
        poll("crm", "http://source", client, archive=archive)
    assert checkpoint("crm") == 0


def test_completed_poll_logs_replayable_manifest(tmp_path):
    archive, logs = Archive(tmp_path), []
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=page([CRM], 1))
    )) as client:
        assert poll("crm", "http://source", client, archive=archive, emit_archive=logs.append) == 1
    manifest = logs[-1]["archive_manifest"]
    assert replay(archive, manifest) == 0
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM revenue_raw.job_runs").fetchone()["n"] == 0
    assert json.loads((tmp_path / f"{manifest}.json").read_text())["kind"] == "completed-poll-v1"
