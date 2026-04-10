from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bson import ObjectId

from app.core.metadata import apply_create_metadata, apply_update_metadata
from app.database import get_database


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _collection(name: str):
    db = get_database()
    return db[name]


def _serialize(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    serialized = dict(document)
    if "_id" in serialized:
        serialized["_id"] = str(serialized["_id"])
    return serialized


def _object_id_or_none(value: str) -> ObjectId | None:
    if not value or not ObjectId.is_valid(value):
        return None
    return ObjectId(value)


def upsert_role(
    *,
    role_code: str,
    role_name: str,
    description: str = "",
    status: str = "active",
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    role_code = _normalize(role_code).lower()
    if not role_code:
        raise ValueError("role_code is required.")

    collection = _collection("roles")
    existing = collection.find_one({"role_code": role_code})
    now = _utc_now_iso()

    payload = {
        "role_code": role_code,
        "role_name": _normalize(role_name) or role_code.replace("_", " ").title(),
        "description": _normalize(description),
        "status": _normalize(status).lower() or "active",
        "updated_at": now,
    }
    payload = apply_update_metadata(payload, actor_user_id)

    if existing:
        collection.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        payload = apply_create_metadata(payload, actor_user_id)
        collection.insert_one(payload)

    return _serialize(collection.find_one({"role_code": role_code}))


def upsert_permission(
    *,
    permission_code: str,
    permission_name: str,
    description: str = "",
    status: str = "active",
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    permission_code = _normalize(permission_code).lower()
    if not permission_code:
        raise ValueError("permission_code is required.")

    collection = _collection("permissions")
    existing = collection.find_one({"permission_code": permission_code})
    payload = {
        "permission_code": permission_code,
        "permission_name": _normalize(permission_name) or permission_code.replace("_", " ").title(),
        "description": _normalize(description),
        "status": _normalize(status).lower() or "active",
    }
    payload = apply_update_metadata(payload, actor_user_id)

    if existing:
        collection.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        payload = apply_create_metadata(payload, actor_user_id)
        collection.insert_one(payload)

    return _serialize(collection.find_one({"permission_code": permission_code}))


def upsert_role_permission(
    *,
    role_code: str,
    permission_code: str,
    status: str = "active",
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    role_code = _normalize(role_code).lower()
    permission_code = _normalize(permission_code).lower()
    if not role_code or not permission_code:
        raise ValueError("role_code and permission_code are required.")

    collection = _collection("role_permissions")
    existing = collection.find_one(
        {"role_code": role_code, "permission_code": permission_code}
    )
    payload = {
        "role_code": role_code,
        "permission_code": permission_code,
        "status": _normalize(status).lower() or "active",
    }
    payload = apply_update_metadata(payload, actor_user_id)

    if existing:
        collection.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        payload = apply_create_metadata(payload, actor_user_id)
        collection.insert_one(payload)

    return _serialize(
        collection.find_one({"role_code": role_code, "permission_code": permission_code})
    )


def assign_role_to_user(
    *,
    user_id: str,
    role_code: str,
    status: str = "active",
    assigned_by: str = "",
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    user_id = _normalize(user_id)
    role_code = _normalize(role_code).lower()
    if not user_id or not role_code:
        raise ValueError("user_id and role_code are required.")

    collection = _collection("user_role_assignments")
    existing = collection.find_one({"user_id": user_id, "role_code": role_code})
    payload = {
        "user_id": user_id,
        "role_code": role_code,
        "status": _normalize(status).lower() or "active",
        "assigned_by": _normalize(assigned_by) or None,
        "assigned_at": _utc_now_iso(),
    }
    payload = apply_update_metadata(payload, actor_user_id)

    if existing:
        collection.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        payload = apply_create_metadata(payload, actor_user_id)
        collection.insert_one(payload)

    return _serialize(collection.find_one({"user_id": user_id, "role_code": role_code}))


def create_workflow_event(
    *,
    project_id: str,
    from_state: str,
    to_state: str,
    status: str = "recorded",
    actor_user_id: str = "",
    actor_role_code: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload = {
        "project_id": _normalize(project_id),
        "from_state": _normalize(from_state).lower(),
        "to_state": _normalize(to_state).lower(),
        "status": _normalize(status).lower() or "recorded",
        "actor_user_id": _normalize(actor_user_id) or None,
        "actor_role_code": _normalize(actor_role_code).lower() or None,
        "context": context or {},
    }
    payload = apply_create_metadata(payload, actor_user_id or None)
    result = _collection("workflow_events").insert_one(payload)
    return _serialize(_collection("workflow_events").find_one({"_id": result.inserted_id}))


def create_vault(
    *,
    vault_code: str,
    vault_type: str,
    project_id: str = "",
    family_id: str = "",
    organization_id: str = "",
    storage_limit_bytes: int = 0,
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    payload = {
        "vault_code": _normalize(vault_code) or f"vault_{uuid4().hex}",
        "vault_type": _normalize(vault_type).lower() or "standard",
        "status": "active",
        "project_id": _normalize(project_id) or None,
        "family_id": _normalize(family_id) or None,
        "organization_id": _normalize(organization_id) or None,
        "storage_limit_bytes": max(int(storage_limit_bytes or 0), 0),
        "storage_used_bytes": 0,
    }
    payload = apply_create_metadata(payload, actor_user_id)
    result = _collection("vaults").insert_one(payload)
    return _serialize(_collection("vaults").find_one({"_id": result.inserted_id}))


def create_vault_file(
    *,
    vault_id: str,
    uploader_id: str,
    category: str,
    checksum: str,
    size_bytes: int,
    project_id: str = "",
    evidence_kind: str = "",
    internal_only: bool = False,
    customer_visible: bool = False,
    verification_status: str = "pending",
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    payload = {
        "file_id": f"vf_{uuid4().hex}",
        "vault_id": _normalize(vault_id),
        "project_id": _normalize(project_id) or None,
        "uploader_id": _normalize(uploader_id),
        "category": _normalize(category),
        "evidence_kind": _normalize(evidence_kind),
        "checksum": _normalize(checksum),
        "internal_only": bool(internal_only),
        "customer_visible": bool(customer_visible),
        "verification_status": _normalize(verification_status).lower() or "pending",
        "size_bytes": max(int(size_bytes or 0), 0),
        "uploaded_at": _utc_now_iso(),
        "last_accessed_at": None,
    }
    payload = apply_create_metadata(payload, actor_user_id)
    result = _collection("vault_files").insert_one(payload)

    if payload["vault_id"]:
        vault_id_query: dict[str, Any] = {"vault_code": payload["vault_id"]}
        object_id = _object_id_or_none(payload["vault_id"])
        if object_id is not None:
            vault_id_query = {"_id": object_id}
        _collection("vaults").update_one(
            vault_id_query,
            {"$inc": {"storage_used_bytes": payload["size_bytes"]}},
        )

    return _serialize(_collection("vault_files").find_one({"_id": result.inserted_id}))


def set_tool_status(
    *,
    tool_code: str,
    status: str,
    severity: str = "info",
    message: str = "",
    context: dict[str, Any] | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    tool_code = _normalize(tool_code).lower()
    if not tool_code:
        raise ValueError("tool_code is required.")

    collection = _collection("tool_status")
    existing = collection.find_one({"tool_code": tool_code})
    payload = {
        "tool_code": tool_code,
        "status": _normalize(status).lower() or "unknown",
        "severity": _normalize(severity).lower() or "info",
        "message": _normalize(message),
        "context": context or {},
    }
    payload = apply_update_metadata(payload, actor_user_id)

    if existing:
        collection.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        payload = apply_create_metadata(payload, actor_user_id)
        collection.insert_one(payload)

    return _serialize(collection.find_one({"tool_code": tool_code}))


def enqueue_failed_workflow(
    *,
    workflow_name: str,
    failed_state: str,
    failure_reason: str,
    project_id: str = "",
    retry_count: int = 0,
    next_retry_at: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    payload = {
        "queue_item_id": f"wfq_{uuid4().hex}",
        "project_id": _normalize(project_id) or None,
        "workflow_name": _normalize(workflow_name),
        "failed_state": _normalize(failed_state).lower(),
        "failure_reason": _normalize(failure_reason),
        "status": "queued",
        "retry_count": max(int(retry_count or 0), 0),
        "next_retry_at": _normalize(next_retry_at) or None,
    }
    payload = apply_create_metadata(payload, actor_user_id)
    result = _collection("failed_workflow_queue").insert_one(payload)
    return _serialize(
        _collection("failed_workflow_queue").find_one({"_id": result.inserted_id})
    )
