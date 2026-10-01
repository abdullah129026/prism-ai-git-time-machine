"""PRISM backend — AI-Powered Git Time Machine API."""

from contextlib import asynccontextmanager
from shutil import which

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analyze, repos

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
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
