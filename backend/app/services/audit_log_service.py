from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from app.core.metadata import apply_create_metadata
from app.database import get_database


def _normalize(value: Any, default: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or default


def write_audit_log(
    *,
    actor_user_id: str | None,
    actor_email: str | None,
    actor_name: str | None,
    action: str,
    target_type: str,
    target_id: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None,
    result: str = "success",
) -> str:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    payload = {
        "action": _normalize(action, "unspecified_action"),
        "actor_user_id": _normalize(actor_user_id) or None,
        "actor_email": _normalize(actor_email).lower() or None,
        "actor_name": _normalize(actor_name) or None,
        "target_type": _normalize(target_type, "system"),
        "target_id": _normalize(target_id, "unknown"),
        "before": before or {},
        "after": after or {},
        "context": context or {},
        "details": details or {},
        "result": _normalize(result, "success").lower(),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    payload = apply_create_metadata(payload, _normalize(actor_user_id) or None)
    result_doc = db.audit_logs.insert_one(payload)
    return str(result_doc.inserted_id)


def create_audit_log(
    action: str,
    actor_user_id: Optional[str],
    entity_type: str,
    entity_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    return write_audit_log(
        actor_user_id=actor_user_id,
        actor_email=None,
        actor_name=None,
        action=action,
        target_type=entity_type,
        target_id=entity_id,
        details=details or {},
    )


def list_audit_logs() -> List[Dict[str, Any]]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    logs: List[Dict[str, Any]] = []

    for log in db.audit_logs.find().sort("timestamp", -1):
        log["_id"] = str(log["_id"])
        logs.append(log)

    return logs
