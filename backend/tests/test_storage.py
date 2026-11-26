"""Tests for the repo storage layer (PRISM v2 item 1).

The storage interface lets a JobStore survive a backend restart: a
second store built against the same directory still serves the repos
and jobs the first one saved, without a re-ingest.
"""

from app.services.git_parser import FileChange, ParsedCommit
from app.services.jobs import JobStore
from app.services.storage import DiskRepoStorage


def _commit(sha):
    return ParsedCommit(sha=sha, message="fix it", author="Ada",
                        author_email="ada@example.com",
                        committed_at="2026-01-01T00:00:00+00:00",
                        parents=[],
                        files=[FileChange(path="a.py", additions=3,
                                          deletions=1)])


def test_store_survives_recreation_against_same_dir(tmp_path):
    # The item 1 done criterion, at store level: recreate the store
    # against the same directory and the repo is still queryable.
    first = JobStore(storage=DiskRepoStorage(tmp_path))
    job = first.create("https://example.com/repo.git", 10)
    first.store_repo(job.repo_id, "https://example.com/repo.git",
                     [_commit("abc")])
    first.update(job.job_id, status="ready", commits_parsed=1)

    second = JobStore(storage=DiskRepoStorage(tmp_path))
    repo = second.get_repo(job.repo_id)
    assert repo is not None
    assert repo["repo_url"] == "https://example.com/repo.git"
    assert [c.sha for c in repo["commits"]] == ["abc"]
    assert repo["commits"][0].files[0].path == "a.py"
    restored = second.get(job.job_id)
    assert restored is not None
    assert restored.status == "ready"
    assert restored.commits_parsed == 1


def test_store_without_storage_is_memory_only():
    # No storage given: today's behaviour, a fresh store sees nothing.
    store = JobStore()
    job = store.create("https://example.com/repo.git", 10)
    store.store_repo(job.repo_id, "https://example.com/repo.git",
                     [_commit("abc")])
    assert JobStore().get_repo(job.repo_id) is None


def test_corrupt_stored_file_is_skipped_not_fatal(tmp_path):
    # A corrupt file on disk must not stop the store from starting:
    # it is skipped, the rest loads.
    (tmp_path / "repos").mkdir()
    (tmp_path / "repos" / "bad.json").write_text("{not json")
    store = JobStore(storage=DiskRepoStorage(tmp_path))
    assert store.get_repo("bad") is None
