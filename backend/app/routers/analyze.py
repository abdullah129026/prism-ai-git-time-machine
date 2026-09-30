"""Analysis routes: timeline, conflict prediction, ownership."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


@router.get("/{repo_id}/timeline")
def timeline(repo_id: str) -> dict:
    # Week 1 (days 3-5): 3D-ready node graph JSON
    raise NotImplementedError


class ConflictRequest(BaseModel):
    base: str
    head: str


@router.post("/{repo_id}/predict-conflict")
def predict_conflict(repo_id: str, body: ConflictRequest) -> dict:
    # Week 2 (days 11-12)
    raise NotImplementedError


@router.get("/{repo_id}/ownership")
def ownership(repo_id: str, path: str | None = None) -> dict:
    # Week 2 (days 13-14)
    raise NotImplementedError
