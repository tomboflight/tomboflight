from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId

from app.config import settings
from app.core.package_catalog import get_package
from app.database import get_database
from app.services.audit_log_service import create_audit_log
from app.services.entitlement_service import resolve_project_entitlements
from app.services.project_membership_service import (
    get_project_access_snapshot,
    list_accessible_project_ids,
)

ALLOWED_KEY_TYPES = {
    "household_invite_key",
    "branch_link_key",
    "viewer_share_key",
}


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _keys_collection():
    db = get_database()
    return db["project_link_keys"]


def _projects_collection():
    db = get_database()
    return db["projects"]


def _entitlements_collection():
    db = get_database()
    return db["project_entitlements"]


def _orders_collection():
    db = get_database()
    return db["orders"]


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _hash_link_key(raw_value: str) -> str:
    payload = f"{settings.secret_key}:link-key:{_normalize_value(raw_value)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _link_key_preview(raw_value: str) -> str:
    del raw_value
    return "********"


def _is_expired(document: dict[str, Any]) -> bool:
    expires_at = _normalize_value(document.get("expires_at"))
    if not expires_at:
        return False
    try:
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except Exception:
        return False
    return expires_dt < _utcnow()


def _project_id_candidates(project_id: str) -> list[Any]:
    values: list[Any] = [str(project_id)]
    oid = _to_object_id(project_id)
    if oid is not None:
        values.append(oid)
    return values


def _is_paid_package_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False

    item_type = _normalize_value(order.get("item_type") or "package").lower()
    status = _normalize_value(order.get("status")).lower()

    return item_type == "package" and status in {
        "paid",
        "complete",
        "completed",
        "succeeded",
    }


def _get_paid_package_order(project_id: str) -> dict[str, Any] | None:
    cursor = _orders_collection().find(
        {"project_id": {"$in": _project_id_candidates(project_id)}}
    ).sort("created_at", -1)

    for order in cursor:
        if _is_paid_package_order(order):
            return order

    return None


def _serialize_key(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None

    key_value = document.get("key_value")
    key_preview = document.get("key_preview")
    if not key_preview and key_value:
        key_preview = _link_key_preview(str(key_value))
    return {
        "_id": document.get("_id"),
        "id": str(document.get("_id")),
        "key_type": str(document.get("key_type") or "branch_link_key"),
        "project_id": str(document.get("project_id") or ""),
        "user_id": str(document.get("user_id") or ""),
        "issuer_user_id": str(document.get("issuer_user_id") or document.get("user_id") or "") or None,
        "target_email": _normalize_value(document.get("target_email")) or None,
        "allowed_role": _normalize_value(document.get("allowed_role")) or None,
        "package_code": document.get("package_code"),
        "package_name": document.get("package_name"),
        "package_lane": document.get("package_lane"),
        "key_value": str(key_value or ""),
        "key_preview": _normalize_value(key_preview) or None,
        "key_hash": _normalize_value(document.get("key_hash")) or None,
        "status": document.get("status", "active"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
        "revoked_at": document.get("revoked_at"),
        "expires_at": document.get("expires_at"),
        "expired_at": document.get("expired_at"),
        "max_uses": int(document.get("max_uses") or 1),
        "use_count": int(document.get("use_count") or 0),
    }


def get_project_by_id(project_id: str) -> dict[str, Any] | None:
    oid = _to_object_id(project_id)
    if oid is None:
        return None
    return _projects_collection().find_one({"_id": oid})


def get_project_summary(project_id: str) -> dict[str, Any] | None:
    project = get_project_by_id(project_id)
    if not project:
        return None

    raw_id = project.get("_id")
    project_id_str = str(raw_id)
    entitlement = _get_project_entitlement(project_id_str)
    paid_order = _get_paid_package_order(project_id_str)
    package_code = str(
        (entitlement or {}).get("package_code")
        or (paid_order or {}).get("package_code")
        or (paid_order or {}).get("package_slug")
        or project.get("package_code")
        or project.get("package_slug")
        or ""
    ).strip()
    package = get_package(package_code) or {}

    return {
        "project_id": str(raw_id),
        "project_name": str(project.get("project_name") or project.get("name") or "Workspace").strip(),
        "owner_user_id": str(project.get("owner_user_id") or "").strip(),
        "owner_email": str(project.get("owner_email") or "").strip(),
        "package_code": package_code or None,
        "package_name": str(
            (entitlement or {}).get("package_name")
            or (paid_order or {}).get("package_name")
            or project.get("package_name")
            or package.get("display_name")
            or ""
        ).strip()
        or None,
        "package_lane": str(
            (entitlement or {}).get("package_lane")
            or project.get("project_lane")
            or package.get("package_lane")
            or ""
        ).strip()
        or None,
        "household_id": str(project.get("household_id") or "").strip() or None,
        "family_id": str(project.get("family_id") or "").strip() or None,
    }


def _can_user_access_project(
    project_id: str,
    *,
    user_id: str = "",
    user_email: str = "",
) -> bool:
    project = get_project_by_id(project_id)
    if not project:
        return False

    access_snapshot = get_project_access_snapshot(
        project,
        user_id=str(user_id or "").strip(),
        email=str(user_email or "").strip().lower(),
    )
    return bool(access_snapshot.get("accessible"))


def _get_project_entitlement(project_id: str) -> dict[str, Any] | None:
    entitlements = _entitlements_collection()
    return entitlements.find_one({"project_id": str(project_id), "status": "active"}) or entitlements.find_one({"project_id": str(project_id)})


def project_supports_link_keys(project_id: str) -> bool:
    entitlement = _get_project_entitlement(project_id)
    if entitlement:
        try:
            resolved = resolve_project_entitlements(
                str(entitlement.get("package_code") or "").strip(),
                list(entitlement.get("active_addons", [])),
            )
        except Exception:
            resolved = entitlement.get("resolved_entitlements") or {}
        if "can_use_link_keys" in resolved:
            return bool(resolved.get("can_use_link_keys"))

    paid_order = _get_paid_package_order(project_id)
    package_code = str(
        (paid_order or {}).get("package_code")
        or (paid_order or {}).get("package_slug")
        or ""
    ).strip()
    package = get_package(package_code) or {}
    return bool(package.get("can_use_link_keys", False))


def user_can_access_project(
    project_id: str,
    user_id: str,
    user_email: str = "",
) -> bool:
    summary = get_project_summary(project_id)
    if not summary:
        return False

    if not _can_user_access_project(
        project_id,
        user_id=user_id,
        user_email=user_email,
    ):
        return False

    return bool(
        _get_project_entitlement(project_id) or _get_paid_package_order(project_id)
    )


def list_accessible_link_key_project_ids(
    user_id: str,
    user_email: str = "",
) -> list[str]:
    project_ids: list[str] = []
    seen: set[str] = set()

    normalized_user_id = str(user_id or "").strip()
    normalized_user_email = str(user_email or "").strip().lower()

    for project_id in list_accessible_project_ids(
        user_id=normalized_user_id,
        email=normalized_user_email,
    ):
        if project_id not in seen and user_can_access_project(
            project_id,
            normalized_user_id,
            normalized_user_email,
        ):
            seen.add(project_id)
            project_ids.append(project_id)

    owner_filters = [
        *([{"owner_user_id": normalized_user_id}] if normalized_user_id else []),
        *([{"owner_email": normalized_user_email}] if normalized_user_email else []),
    ]

    if owner_filters:
        cursor = _projects_collection().find({"$or": owner_filters})
        for item in cursor:
            project_id = str(item.get("_id") or "")
            if project_id and project_id not in seen and user_can_access_project(
                project_id,
                normalized_user_id,
                normalized_user_email,
            ):
                seen.add(project_id)
                project_ids.append(project_id)

    return project_ids


def get_active_key_doc_for_project(project_id: str) -> dict[str, Any] | None:
    active = _keys_collection().find_one(
        {
            "project_id": str(project_id),
            "status": "active",
        },
        sort=[("created_at", -1)],
    )
    if active and _is_expired(active):
        now = _utcnow_iso()
        _keys_collection().update_one(
            {"_id": active["_id"]},
            {"$set": {"status": "expired", "expired_at": now, "updated_at": now}},
        )
        try:
            create_audit_log(
                "link_key_expired",
                None,
                "project_link_key",
                str(active.get("_id")),
                {"project_id": _normalize_value(active.get("project_id"))},
            )
        except Exception:
            pass
        return None
    return active


def get_active_key_for_project(project_id: str) -> dict[str, Any] | None:
    return _serialize_key(get_active_key_doc_for_project(project_id))


def get_key_doc_by_value(key_value: str) -> dict[str, Any] | None:
    normalized = str(key_value or "").strip()
    if not normalized:
        return None
    key_hash = _hash_link_key(normalized)
    document = _keys_collection().find_one({"key_hash": key_hash, "status": "active"})
    if document is None:
        document = _keys_collection().find_one({"key_value": normalized, "status": "active"})
        if document is not None:
            now = _utcnow_iso()
            _keys_collection().update_one(
                {"_id": document["_id"]},
                {
                    "$set": {
                        "key_hash": key_hash,
                        "key_preview": _link_key_preview(normalized),
                        "key_value": None,
                        "updated_at": now,
                    }
                },
            )
            document["key_hash"] = key_hash
            document["key_preview"] = _link_key_preview(normalized)
    if document is not None and _is_expired(document):
        now = _utcnow_iso()
        _keys_collection().update_one(
            {"_id": document["_id"]},
            {"$set": {"status": "expired", "expired_at": now, "updated_at": now}},
        )
        try:
            create_audit_log(
                "link_key_expired",
                None,
                "project_link_key",
                str(document.get("_id")),
                {"project_id": _normalize_value(document.get("project_id"))},
            )
        except Exception:
            pass
        return None
    return document


def list_link_keys_for_user(
    user_id: str,
    *,
    user_email: str = "",
    project_id: str | None = None,
    include_revoked: bool = True,
) -> list[dict[str, Any]]:
    if project_id:
        if not user_can_access_project(project_id, user_id, user_email):
            return []
        owned_project_ids = [str(project_id)]
    else:
        owned_project_ids = list_accessible_link_key_project_ids(user_id, user_email)

    if not owned_project_ids:
        return []

    query: dict[str, Any] = {"project_id": {"$in": owned_project_ids}}
    if not include_revoked:
        query["status"] = "active"

    cursor = _keys_collection().find(query).sort("created_at", -1)
    return [item for item in (_serialize_key(doc) for doc in cursor) if item is not None]


def _generate_raw_link_key() -> str:
    return f"tolk_{secrets.token_hex(12)}"


def generate_link_key(
    *,
    project_id: str,
    user_id: str,
    user_email: str = "",
    allow_admin: bool = False,
    key_type: str = "branch_link_key",
    target_email: str = "",
    allowed_role: str = "",
    max_uses: int = 1,
) -> dict[str, Any]:
    normalized_key_type = _normalize_value(key_type).lower() or "branch_link_key"
    if normalized_key_type not in ALLOWED_KEY_TYPES:
        raise ValueError("Invalid key type.")
    if not allow_admin and not user_can_access_project(project_id, user_id, user_email):
        raise PermissionError("Not authorized to generate a link key for this project.")

    if not project_supports_link_keys(project_id):
        raise ValueError("This package does not include link capabilities.")

    project_summary = get_project_summary(project_id)
    if not project_summary:
        raise ValueError("Project not found.")

    keys = _keys_collection()
    now = _utcnow_iso()

    keys.update_many(
        {"project_id": str(project_id), "status": "active", "key_type": normalized_key_type},
        {"$set": {"status": "revoked", "revoked_at": now, "updated_at": now}},
    )

    document = {
        "key_type": normalized_key_type,
        "project_id": str(project_id),
        "user_id": str(user_id),
        "issuer_user_id": str(user_id),
        "target_email": _normalize_value(target_email).lower() or None,
        "allowed_role": _normalize_value(allowed_role) or None,
        "package_code": project_summary.get("package_code"),
        "package_name": project_summary.get("package_name"),
        "package_lane": project_summary.get("package_lane"),
        "key_value": None,
        "key_hash": None,
        "key_preview": None,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "revoked_at": None,
        "expires_at": None,
        "expired_at": None,
        "max_uses": max(1, int(max_uses or 1)),
        "use_count": 0,
    }
    raw_key = _generate_raw_link_key()
    document["key_hash"] = _hash_link_key(raw_key)
    document["key_preview"] = _link_key_preview(raw_key)
    expiration_hours = max(0, int(settings.link_key_expire_hours or 0))
    if expiration_hours > 0:
        document["expires_at"] = (_utcnow() + timedelta(hours=expiration_hours)).isoformat()

    result = keys.insert_one(document)
    document["_id"] = result.inserted_id
    try:
        create_audit_log(
            "link_key_created",
            str(user_id or "") or None,
            "project_link_key",
            str(result.inserted_id),
            {"project_id": str(project_id), "key_type": normalized_key_type},
        )
    except Exception:
        pass
    serialized = _serialize_key(document) or {}
    serialized["key_value"] = raw_key
    return serialized


def revoke_link_key(
    *,
    key_id: str,
    actor_user_id: str,
    actor_user_email: str = "",
    allow_admin: bool = False,
) -> dict[str, Any] | None:
    oid = _to_object_id(key_id)
    if oid is None:
        return None

    keys = _keys_collection()
    document = keys.find_one({"_id": oid})
    if not document:
        return None

    project_id = str(document.get("project_id") or "")
    if not allow_admin and not user_can_access_project(
        project_id,
        actor_user_id,
        actor_user_email,
    ):
        raise PermissionError("Not authorized to revoke this link key.")

    now = _utcnow_iso()
    keys.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "revoked",
                "revoked_at": now,
                "updated_at": now,
            }
        },
    )

    updated = keys.find_one({"_id": oid})
    try:
        create_audit_log(
            "link_key_revoked",
            str(actor_user_id or "") or None,
            "project_link_key",
            str(oid),
            {"project_id": project_id},
        )
    except Exception:
        pass
    return _serialize_key(updated)
