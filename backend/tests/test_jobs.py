"""Tests for the job store and the background ingest runner."""

from app.services import git_parser
from app.services.jobs import repo_dir, run_ingest, store


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
