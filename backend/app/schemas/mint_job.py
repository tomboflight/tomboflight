from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunNextMintJobPayload(BaseModel):
    worker_id: str = Field(default="api-worker", min_length=1)


class MintJobResponse(BaseModel):
    id: str
    project_id: str
    mint_record_id: str
    job_type: str
    status: str
    attempt_count: int
    max_attempts: int
    priority: int
    run_after: datetime
    locked_by: str | None = None
    locked_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
