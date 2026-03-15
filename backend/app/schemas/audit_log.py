from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    action: str = Field(..., min_length=1, max_length=100)
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: str = Field(..., min_length=1)
    actor_user_id: str | None = None
    actor_email: str | None = None
    actor_name: str | None = None
    details: dict = Field(default_factory=dict)


class AuditLogResponse(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    actor_user_id: str | None = None
    actor_email: str | None = None
    actor_name: str | None = None
    details: dict
    created_at: str


def build_audit_log_response(data: dict) -> AuditLogResponse:
    return AuditLogResponse(
        id=str(data.get("_id", "")),
        action=data["action"],
        entity_type=data["entity_type"],
        entity_id=data["entity_id"],
        actor_user_id=data.get("actor_user_id"),
        actor_email=data.get("actor_email"),
        actor_name=data.get("actor_name"),
        details=data.get("details", {}),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )