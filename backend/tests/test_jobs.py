"""Tests for the job store and the background ingest runner."""

import json
from pathlib import Path
from types import SimpleNamespace

from app.services import git_parser, jobs
from app.services.intent import INTENT_CACHE_VERSION, CommitIntent
from app.services.jobs import repo_dir, run_ingest, store


def _settings_with_data_dir(tmp_path):
    return SimpleNamespace(data_dir=tmp_path)


def _intent(sha, cache_version=INTENT_CACHE_VERSION):
    return CommitIntent(sha=sha, why="fix a crash", bug_fixed="null deref",
                        risk="none", confidence=0.9,
                        cache_version=cache_version)


def test_get_intent_drops_stale_disk_entry_even_when_unlink_fails(
        monkeypatch, tmp_path):
    # A stale on-disk entry whose delete fails must still read as a miss,
    # never raise: the disk cache is best-effort, the caller just re-analyzes.
    monkeypatch.setattr(jobs, "get_settings",
                        lambda: _settings_with_data_dir(tmp_path))
    stale = tmp_path / "intents" / "repo-a" / "deadbeef.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps(
        _intent("deadbeef", cache_version=0).to_dict()))

    def _boom(self):
        raise OSError("disk is read-only")

    monkeypatch.setattr(Path, "unlink", _boom)
    assert store.get_intent("repo-a", "deadbeef") is None
    assert stale.exists()  # the failed delete left the file behind


def test_set_intent_keeps_memory_cache_when_disk_write_fails(
        monkeypatch, tmp_path):
    # Disk is best-effort: a failed write must not lose the in-memory entry
    # the rest of the request is about to read back.
    monkeypatch.setattr(jobs, "get_settings",
                        lambda: _settings_with_data_dir(tmp_path))

    def _boom(self, data, *args, **kwargs):
        raise OSError("disk is read-only")

    monkeypatch.setattr(Path, "write_text", _boom)
    intent = _intent("abc123")
    store.set_intent("repo-disk", "abc123", intent)
    assert store.get_intent("repo-disk", "abc123") is intent


def test_list_intents_scopes_to_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "get_settings",
                        lambda: _settings_with_data_dir(tmp_path))
    store.set_intent("repo-a", "sha1", _intent("sha1"))
    store.set_intent("repo-a", "sha2", _intent("sha2"))
    store.set_intent("repo-b", "sha1", _intent("sha1"))
    assert {i.sha for i in store.list_intents("repo-a")} == {"sha1", "sha2"}
    assert {i.sha for i in store.list_intents("repo-b")} == {"sha1"}


def test_update_unknown_job_is_noop():
    # Updating a job that doesn't exist must not raise.
    store.update("no-such-job", status="ready")
    assert store.get("no-such-job") is None


def test_run_ingest_unknown_job_returns():
    assert run_ingest("no-such-job") is None


def test_run_ingest_records_failure_on_job():
    # gopher:// is rejected by URL validation without any DNS or network —
    # the point under test is the "never raises" contract: the failure is
    # recorded on the job so GET /repos/{job_id} can report it.
    job = store.create("gopher://example.com/repo.git", 10)
    run_ingest(job.job_id)
    updated = store.get(job.job_id)
    assert updated.status == "error"
    assert updated.finished_at is not None
    assert updated.error
    assert "scheme" in updated.error


def test_failed_ingest_removes_partial_clone(monkeypatch):
    # A clone that dies halfway must not leave a partial repo dir behind:
    # failed ingests would otherwise accumulate disk silently.
    def _fail_mid_clone(url, dest, **kwargs):
        dest.mkdir(parents=True)
        (dest / "partial").write_text("half-cloned")
        raise RuntimeError("clone died halfway")

    monkeypatch.setattr(git_parser, "clone_repo", _fail_mid_clone)
    job = store.create("https://example.com/repo.git", 10)
    run_ingest(job.job_id)
    assert store.get(job.job_id).status == "error"
    assert not repo_dir(job.repo_id).exists()
