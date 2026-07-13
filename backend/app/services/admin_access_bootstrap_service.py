from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.admin_permission_registry import (
    CEO_MASTER_ADMIN_EMAIL,
    OFFICER_PROFILE_FIELDS,
    PERMISSION_REGISTRY,
    ROLE_METADATA,
    ROLE_PERMISSION_MAP,
    normalized_officer_role_mapping,
)
from app.database import get_database


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _upsert_role_documents(db, now_iso: str) -> dict[str, int]:
    created = 0
    updated = 0
    roles = db["roles"]
    for role_code, metadata in ROLE_METADATA.items():
        payload = {
            "role_code": role_code,
            "role_name": metadata.get("name") or role_code.replace("_", " ").title(),
            "description": metadata.get("description") or "",
            "status": "active",
            "updated_at": now_iso,
        }
        result = roles.update_one(
            {"role_code": role_code},
            {"$set": payload, "$setOnInsert": {"created_at": now_iso}},
            upsert=True,
        )
        created += int(bool(result.upserted_id))
        if result.matched_count:
            updated += int(bool(result.modified_count))
    return {"created": created, "updated": updated}


def _upsert_permission_documents(db, now_iso: str) -> dict[str, int]:
    created = 0
    updated = 0
    permissions = db["permissions"]
    for permission_code, metadata in PERMISSION_REGISTRY.items():
        payload = {
            "permission_code": permission_code,
            "permission_name": metadata.get("name") or permission_code.replace(".", " ").title(),
            "description": metadata.get("description") or "",
            "status": "active",
            "updated_at": now_iso,
        }
        result = permissions.update_one(
            {"permission_code": permission_code},
            {"$set": payload, "$setOnInsert": {"created_at": now_iso}},
            upsert=True,
        )
        created += int(bool(result.upserted_id))
        if result.matched_count:
            updated += int(bool(result.modified_count))
    return {"created": created, "updated": updated}


def _upsert_role_permission_documents(db, now_iso: str) -> dict[str, int]:
    created = 0
    updated = 0
    role_permissions = db["role_permissions"]
    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        for permission_code in permission_codes:
            if permission_code == "*":
                continue
            payload = {
                "role_code": role_code,
                "permission_code": permission_code,
                "status": "active",
                "updated_at": now_iso,
            }
            result = role_permissions.update_one(
                {"role_code": role_code, "permission_code": permission_code},
                {"$set": payload, "$setOnInsert": {"created_at": now_iso}},
                upsert=True,
            )
            created += int(bool(result.upserted_id))
            if result.matched_count:
                updated += int(bool(result.modified_count))
    return {"created": created, "updated": updated}


def _sync_officer_assignments(db, now_iso: str) -> dict[str, Any]:
    users = db["users"]
    assignments = db["user_role_assignments"]
    mapping = normalized_officer_role_mapping()
    required_role_codes = set(role_code for role_codes in mapping.values() for role_code in role_codes)

    updated_users = 0
    missing_users: list[str] = []
    assignments_created = 0
    assignments_updated = 0
    assignments_disabled = 0

    ceo_master_admin_user_id = ""
    for email, expected_roles in mapping.items():
        user = users.find_one({"email": email})
        if user is None:
            missing_users.append(email)
            continue

        profile_fields = OFFICER_PROFILE_FIELDS.get(email, {})
        update_payload = {
            "email": email,
            "role": "admin",
            "account_type": "business_admin",
            "status": "active",
            "updated_at": now_iso,
        }
        if profile_fields.get("full_name"):
            update_payload["full_name"] = profile_fields["full_name"]
        if profile_fields.get("business_title"):
            update_payload["business_title"] = profile_fields["business_title"]
        if profile_fields.get("access_tier"):
            update_payload["access_tier"] = profile_fields["access_tier"]
        if profile_fields.get("department_role"):
            update_payload["department_role"] = profile_fields["department_role"]

        update_result = users.update_one({"_id": user["_id"]}, {"$set": update_payload})
        updated_users += int(bool(update_result.modified_count))
        user_id = _normalize(user.get("_id"))
        if not user_id:
            continue
        if email == CEO_MASTER_ADMIN_EMAIL:
            ceo_master_admin_user_id = user_id

        for role_code in expected_roles:
            payload = {
                "user_id": user_id,
                "role_code": role_code,
                "status": "active",
                "assigned_by": "system.bootstrap.admin_access",
                "assigned_at": now_iso,
                "updated_at": now_iso,
            }
            result = assignments.update_one(
                {"user_id": user_id, "role_code": role_code},
                {"$set": payload, "$setOnInsert": {"created_at": now_iso}},
                upsert=True,
            )
            assignments_created += int(bool(result.upserted_id))
            if result.matched_count:
                assignments_updated += int(bool(result.modified_count))

        stale_filter = {
            "user_id": user_id,
            "role_code": {"$in": list(required_role_codes - set(expected_roles))},
            "status": {"$in": ["active", "enabled", ""]},
        }
        if stale_filter["role_code"]["$in"]:
            stale_result = assignments.update_many(
                stale_filter,
                {"$set": {"status": "inactive", "updated_at": now_iso}},
            )
            assignments_disabled += int(stale_result.modified_count)

    if ceo_master_admin_user_id:
        singleton_targets: list[str] = []
        if hasattr(assignments, "find"):
            for record in assignments.find(
                {
                    "role_code": {"$in": ["ceo_master_admin", "ceo_super_admin"]},
                    "status": {"$in": ["active", "enabled", ""]},
                }
            ):
                user_id = _normalize(record.get("user_id"))
                if user_id and user_id != ceo_master_admin_user_id:
                    singleton_targets.append(user_id)
        else:
            for record in (getattr(assignments, "documents", None) or []):
                role_code = _normalize(record.get("role_code")).lower()
                status = _normalize(record.get("status")).lower()
                user_id = _normalize(record.get("user_id"))
                if (
                    role_code in {"ceo_master_admin", "ceo_super_admin"}
                    and status in {"active", "enabled", ""}
                    and user_id
                    and user_id != ceo_master_admin_user_id
                ):
                    singleton_targets.append(user_id)
        singleton_targets = sorted(set(singleton_targets))
        if singleton_targets:
            singleton_result = assignments.update_many(
                {
                    "role_code": {"$in": ["ceo_master_admin", "ceo_super_admin"]},
                    "user_id": {"$in": singleton_targets},
                    "status": {"$in": ["active", "enabled", ""]},
                },
                {"$set": {"status": "inactive", "updated_at": now_iso}},
            )
            assignments_disabled += int(singleton_result.modified_count)

    return {
        "updated_users": updated_users,
        "missing_users": missing_users,
        "assignments_created": assignments_created,
        "assignments_updated": assignments_updated,
        "assignments_disabled": assignments_disabled,
        "ceo_master_admin_user_id": ceo_master_admin_user_id or None,
    }


def bootstrap_admin_access_controls() -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise ValueError("Database is not connected.")

    now_iso = _now_iso()
    role_stats = _upsert_role_documents(db, now_iso)
    permission_stats = _upsert_permission_documents(db, now_iso)
    role_permission_stats = _upsert_role_permission_documents(db, now_iso)
    officer_stats = _sync_officer_assignments(db, now_iso)

    return {
        "roles": role_stats,
        "permissions": permission_stats,
        "role_permissions": role_permission_stats,
        "officers": officer_stats,
    }
