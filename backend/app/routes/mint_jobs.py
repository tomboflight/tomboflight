from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_permission
from app.schemas.mint_job import RunNextMintJobPayload
from app.services.mint_job_service import ensure_mint_job_indexes, run_next_job

router = APIRouter(prefix="/mint-jobs", tags=["Mint Jobs"])


def initialize_mint_job_indexes() -> None:
    ensure_mint_job_indexes()


@router.post("/run-next")
def run_next_mint_job(
    payload: RunNextMintJobPayload,
    current_user: dict = Depends(require_permission("admin.access")),
):
    del current_user
    return run_next_job(payload.worker_id)
