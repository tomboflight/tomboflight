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
    target_type: str | None = None
    target_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    context: dict = Field(default_factory=dict)
    result: str = "success"


class AuditLogResponse(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    target_type: str
    target_id: str
    actor_user_id: str | None = None
    actor_email: str | None = None
    actor_name: str | None = None
    details: dict
    before: dict
    after: dict
    context: dict
    result: str
    timestamp: str
    created_at: str


def build_audit_log_response(data: dict) -> AuditLogResponse:
    target_type = data.get("target_type") or data.get("entity_type") or "system"
    target_id = data.get("target_id") or data.get("entity_id") or "unknown"
    timestamp = data.get("timestamp") or data.get("created_at")

    return AuditLogResponse(
        id=str(data.get("_id", "")),
        action=data["action"],
        entity_type=str(data.get("entity_type") or target_type),
        entity_id=str(data.get("entity_id") or target_id),
        target_type=str(target_type),
        target_id=str(target_id),
        actor_user_id=data.get("actor_user_id"),
        actor_email=data.get("actor_email"),
        actor_name=data.get("actor_name"),
        details=data.get("details", {}),
        before=data.get("before", {}) or {},
        after=data.get("after", {}) or {},
        context=data.get("context", {}) or {},
        result=str(data.get("result") or "success"),
        timestamp=str(timestamp or datetime.now(UTC).isoformat()),
        created_at=str(data.get("created_at") or timestamp or datetime.now(UTC).isoformat()),
    )
