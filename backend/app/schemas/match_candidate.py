from datetime import UTC, datetime
from pydantic import BaseModel, Field

from app.core.state_catalog import normalize_approval_state


class MatchCandidateCreate(BaseModel):
    member_id_a: str = Field(..., min_length=1)
    member_id_b: str = Field(..., min_length=1)
    score: float = Field(..., ge=0, le=100)
    status: str = Field(default="pending", min_length=1, max_length=50)
    reasons: list[str] = []
    canonical_person_id: str | None = None


class MatchCandidateResponse(BaseModel):
    id: str
    member_id_a: str
    member_id_b: str
    score: float
    status: str
    reasons: list[str]
    canonical_person_id: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    created_at: str


def build_match_candidate_response(data: dict) -> MatchCandidateResponse:
    return MatchCandidateResponse(
        id=str(data.get("_id", "")),
        member_id_a=data["member_id_a"],
        member_id_b=data["member_id_b"],
        score=data["score"],
        status=normalize_approval_state(data.get("status"), default="pending"),
        reasons=data.get("reasons", []),
        canonical_person_id=data.get("canonical_person_id"),
        approved_by=data.get("approved_by"),
        approved_at=data.get("approved_at"),
        rejected_by=data.get("rejected_by"),
        rejected_at=data.get("rejected_at"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
