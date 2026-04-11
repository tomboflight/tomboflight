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


def _as_string(value: object, default: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _serialize_created_at(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return _as_string(value, datetime.now(UTC).isoformat())


def _legacy_entity_fields(data: dict) -> tuple[str, str]:
    for key in (
        "relationship_id",
        "member_id",
        "family_id",
        "project_id",
        "upload_id",
        "order_id",
        "user_id",
    ):
        value = _as_string(data.get(key))
        if value:
            return key.removesuffix("_id"), value

    return "audit_event", _as_string(data.get("_id"))


def _details(data: dict) -> dict:
    details = data.get("details")
    if isinstance(details, dict):
        return details

    excluded = {
        "_id",
        "action",
        "event",
        "entity_type",
        "entity_id",
        "actor_user_id",
        "actor_email",
        "actor_name",
        "created_at",
    }
    return {key: value for key, value in data.items() if key not in excluded}


def build_audit_log_response(data: dict) -> AuditLogResponse:
    legacy_entity_type, legacy_entity_id = _legacy_entity_fields(data)
    timestamp = data.get("timestamp") or data.get("created_at")
    target_type = _as_string(
        data.get("target_type") or data.get("entity_type"),
        legacy_entity_type or "system",
    )
    target_id = _as_string(
        data.get("target_id") or data.get("entity_id"),
        legacy_entity_id or "unknown",
    )
    actor_name = (
        _as_string(data.get("actor_name"))
        or _as_string(data.get("created_by"))
        or _as_string(data.get("deleted_by"))
        or None
    )

    return AuditLogResponse(
        id=str(data.get("_id", "")),
        action=_as_string(data.get("action") or data.get("event"), "legacy_event"),
        entity_type=_as_string(data.get("entity_type"), target_type),
        entity_id=_as_string(data.get("entity_id"), target_id),
        target_type=target_type,
        target_id=target_id,
        actor_user_id=_as_string(data.get("actor_user_id")) or None,
        actor_email=_as_string(data.get("actor_email")) or None,
        actor_name=actor_name,
        details=_details(data),
        before=data.get("before", {}) or {},
        after=data.get("after", {}) or {},
        context=data.get("context", {}) or {},
        result=str(data.get("result") or "success"),
        timestamp=_serialize_created_at(timestamp),
        created_at=_serialize_created_at(data.get("created_at") or timestamp),
    )
