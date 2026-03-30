from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
from app.schemas.mint_job import RunNextMintJobPayload
from app.services.mint_job_service import ensure_mint_job_indexes, run_next_job

router = APIRouter(prefix="/mint-jobs", tags=["Mint Jobs"])


@router.on_event("startup")
def startup_mint_job_indexes():
    ensure_mint_job_indexes()


@router.post("/run-next")
def run_next_mint_job(
    payload: RunNextMintJobPayload,
    current_user: dict = Depends(require_admin),
):
    del current_user
    return run_next_job(payload.worker_id)
