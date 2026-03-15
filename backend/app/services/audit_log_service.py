from typing import Any, Dict, List, Optional

from app.core.metadata import apply_create_metadata
from app.database import get_database


def create_audit_log(
    action: str,
    actor_user_id: Optional[str],
    entity_type: str,
    entity_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    payload = {
        "action": action,
        "actor_user_id": actor_user_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {},
    }

    payload = apply_create_metadata(payload, actor_user_id)
    result = db.audit_logs.insert_one(payload)
    return str(result.inserted_id)


def list_audit_logs() -> List[Dict[str, Any]]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    logs: List[Dict[str, Any]] = []

    for log in db.audit_logs.find().sort("created_at", -1):
        log["_id"] = str(log["_id"])
        logs.append(log)

    return logs