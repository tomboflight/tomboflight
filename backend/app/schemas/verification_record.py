from datetime import UTC, datetime
from pydantic import BaseModel, Field


class VerificationRecordCreate(BaseModel):
    relationship_id: str | None = None
    canonical_person_id: str | None = None
    record_type: str = Field(..., min_length=1, max_length=100)
    document_url: str = Field(..., min_length=1, max_length=500)
    verification_status: str = Field(default="pending", min_length=1, max_length=50)
    verified_by: str | None = None
    notes: str | None = None


class VerificationRecordResponse(BaseModel):
    id: str
    relationship_id: str | None = None
    canonical_person_id: str | None = None
    record_type: str
    document_url: str
    verification_status: str
    verified_by: str | None = None
    notes: str | None = None
    created_at: str


def build_verification_record_response(data: dict) -> VerificationRecordResponse:
    return VerificationRecordResponse(
        id=str(data.get("_id", "")),
        relationship_id=data.get("relationship_id"),
        canonical_person_id=data.get("canonical_person_id"),
        record_type=data["record_type"],
        document_url=data["document_url"],
        verification_status=data.get("verification_status", "pending"),
        verified_by=data.get("verified_by"),
        notes=data.get("notes"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )