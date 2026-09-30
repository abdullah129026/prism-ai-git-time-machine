"""PRISM backend — AI-Powered Git Time Machine API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analyze, repos

app = FastAPI(
    title="PRISM API",
    description="AI-Powered Git Time Machine — intent-aware git history API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened in production via env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos.router, prefix="/repos", tags=["repos"])
app.include_router(analyze.router, prefix="/repos", tags=["analyze"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "prism-api"}
