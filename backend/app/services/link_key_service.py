from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.package_catalog import get_package
from app.database import get_database
from app.services.entitlement_service import resolve_project_entitlements
from app.services.project_membership_service import (
    get_project_access_snapshot,
    list_accessible_project_ids,
)


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

    return {
        "_id": document.get("_id"),
        "id": str(document.get("_id")),
        "project_id": str(document.get("project_id") or ""),
        "user_id": str(document.get("user_id") or ""),
        "package_code": document.get("package_code"),
        "package_name": document.get("package_name"),
        "package_lane": document.get("package_lane"),
        "key_value": document.get("key_value"),
        "status": document.get("status", "active"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
        "revoked_at": document.get("revoked_at"),
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


def list_owned_project_ids(user_id: str, user_email: str = "") -> list[str]:
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

    owner_filters: dict[str, Any] = {}
    if normalized_user_id:
        owner_filters.setdefault("$or", []).append({"owner_user_id": normalized_user_id})
    if normalized_user_email:
        owner_filters.setdefault("$or", []).append({"owner_email": normalized_user_email})

    if owner_filters.get("$or"):
        cursor = _projects_collection().find(owner_filters)
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
    return _keys_collection().find_one(
        {
            "project_id": str(project_id),
            "status": "active",
        },
        sort=[("created_at", -1)],
    )


def get_active_key_for_project(project_id: str) -> dict[str, Any] | None:
    return _serialize_key(get_active_key_doc_for_project(project_id))


def get_key_doc_by_value(key_value: str) -> dict[str, Any] | None:
    return _keys_collection().find_one(
        {
            "key_value": str(key_value or "").strip(),
            "status": "active",
        }
    )


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
        owned_project_ids = list_owned_project_ids(user_id, user_email)

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
) -> dict[str, Any]:
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
        {"project_id": str(project_id), "status": "active"},
        {
            "$set": {
                "status": "revoked",
                "revoked_at": now,
                "updated_at": now,
            }
        },
    )

    document = {
        "project_id": str(project_id),
        "user_id": str(user_id),
        "package_code": project_summary.get("package_code"),
        "package_name": project_summary.get("package_name"),
        "package_lane": project_summary.get("package_lane"),
        "key_value": _generate_raw_link_key(),
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "revoked_at": None,
    }

    result = keys.insert_one(document)
    document["_id"] = result.inserted_id
    return _serialize_key(document) or {}


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
    return _serialize_key(updated)
