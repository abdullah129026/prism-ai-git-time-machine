"""PRISM backend — AI-Powered Git Time Machine API."""

import json
import logging
import threading
from contextlib import asynccontextmanager
from shutil import which

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.middleware import (
    HostGuardMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.routers import analyze, repos
from app.services import git_parser
from app.services.jobs import run_ingest, store

settings = get_settings()
logger = logging.getLogger("prism.demo")

# Cap on commits parsed for the pre-loaded demo repo: fast cold start.
DEMO_MAX_COMMITS = 500


def _seed_demo(cfg: Settings) -> None:
    """Kick off the demo-repo ingest in the background, once per process.

    A fresh process always has an empty in-memory job store, so a marker left
    by a previous run points at a repo that no longer exists in memory — drop
    it and re-seed. The marker is only rewritten after a successful ingest, so
    a failed seed retries on the next start instead of going stale.
    """
    url = cfg.demo_repo.strip()
    if not url:
        return
    marker = cfg.data_dir / "demo.json"
    marker.unlink(missing_ok=True)
    try:
        repo_url = git_parser.validate_repo_url(url)
    except ValueError:
        logger.warning("PRISM_DEMO_REPO is not a valid repo URL; skipping demo seed")
        return
    job = store.create(repo_url, min(DEMO_MAX_COMMITS, cfg.max_commits))

    def _run() -> None:
        run_ingest(job.job_id)
        done = store.get(job.job_id)
        if done is None or done.status != "ready":
            return
        try:
            marker.write_text(
                json.dumps({"repo_id": done.repo_id, "repo_url": repo_url})
            )
        except OSError:
            pass  # marker is best-effort; /repos/demo degrades to "seeding"

    threading.Thread(target=_run, daemon=True, name="prism-demo-seed").start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    _seed_demo(cfg)
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Git Time Machine — intent-aware git history API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last so they run first (outermost): reject bad hosts, then rate
# limit, then stamp security headers on the way out.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    ingest_per_hour=settings.rate_limit_ingest_per_hour,
    intent_per_hour=settings.rate_limit_intent_per_hour,
)
app.add_middleware(
    HostGuardMiddleware, allowed_hosts=settings.trusted_host_list)

app.include_router(repos.router, prefix="/repos", tags=["repos"])
app.include_router(analyze.router, prefix="/repos", tags=["analyze"])


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }


@app.get("/health")
def health() -> dict:
    """Liveness probe: the process is up and serving."""
    return {"status": "ok", "service": "prism-api", "version": settings.app_version}


@app.get("/ready")
def ready() -> dict:
    """Readiness probe: dependencies needed to serve traffic are present."""
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        data_dir_ok = settings.data_dir.is_dir()
    except OSError:
        data_dir_ok = False
    checks = {
        "data_dir_writable": data_dir_ok,
        "git_available": which("git") is not None,
    }
    return {"ready": all(checks.values()), "checks": checks}
