from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database
from app.schemas.vault import (
    VaultAccessGrantCreate,
    VaultCollectionCreate,
    VaultItemCreate,
    VaultItemUpdate,
    VaultReleaseRuleCreate,
)


def _col(name: str) -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db[name])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return str(value or "").strip()


def _find_by_id(collection_name: str, item_id: str) -> dict[str, Any] | None:
    col = _col(collection_name)
    if ObjectId.is_valid(item_id):
        doc = col.find_one({"_id": ObjectId(item_id)})
    else:
        doc = col.find_one({"_id": item_id})
    return cast(dict[str, Any] | None, doc)


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    result = dict(doc)
    result["id"] = _str_id(doc.get("_id"))
    result.pop("_id", None)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Vault Items
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_item(payload: VaultItemCreate, owner_user_id: str) -> dict[str, Any]:
    col = _col("vault_items")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "owner_user_id": owner_user_id,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    log_vault_audit_event(_str_id(result.inserted_id), owner_user_id, "create")
    return _serialize(doc) or {}


def get_vault_item(item_id: str, requesting_user_id: str) -> dict[str, Any] | None:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        return None

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner == requesting_user_id:
        log_vault_audit_event(item_id, requesting_user_id, "view")
        return _serialize(doc)

    # Check access grants
    grant = _col("vault_access_grants").find_one({
        "vault_item_id": item_id,
        "grantee_user_id": requesting_user_id,
    })
    if grant:
        log_vault_audit_event(item_id, requesting_user_id, "view")
        return _serialize(doc)

    raise ValueError("Access denied.")


def update_vault_item(
    item_id: str,
    updates: VaultItemUpdate,
    requesting_user_id: str,
) -> dict[str, Any] | None:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        raise ValueError("Vault item not found.")

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner != requesting_user_id:
        grant = _col("vault_access_grants").find_one({
            "vault_item_id": item_id,
            "grantee_user_id": requesting_user_id,
            "permission_role": {"$in": ["steward"]},
        })
        if not grant:
            raise PermissionError("Only the owner or steward can update this item.")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = _now()

    col = _col("vault_items")
    if ObjectId.is_valid(item_id):
        col.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})
    else:
        col.update_one({"_id": item_id}, {"$set": update_data})

    return _serialize(_find_by_id("vault_items", item_id))


def delete_vault_item(item_id: str, requesting_user_id: str) -> bool:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        raise ValueError("Vault item not found.")

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner != requesting_user_id:
        raise PermissionError("Only the owner can delete this item.")

    col = _col("vault_items")
    if ObjectId.is_valid(item_id):
        col.delete_one({"_id": ObjectId(item_id)})
    else:
        col.delete_one({"_id": item_id})

    log_vault_audit_event(item_id, requesting_user_id, "delete")
    return True


def list_vault_items(
    project_id: str,
    requesting_user_id: str,
    vault_scope: str | None = None,
) -> list[dict[str, Any]]:
    col = _col("vault_items")
    query: dict[str, Any] = {
        "$or": [
            {"owner_user_id": requesting_user_id, "project_id": project_id},
            {"vault_item_id": {"$exists": True}},
        ]
    }

    # Items owned by user for this project
    owned_query: dict[str, Any] = {"owner_user_id": requesting_user_id, "project_id": project_id}
    if vault_scope:
        owned_query["vault_scope"] = vault_scope

    owned_items = list(col.find(owned_query))
    owned_ids = {_str_id(doc.get("_id")) for doc in owned_items}

    # Items with grants for this user
    grants = list(_col("vault_access_grants").find({"grantee_user_id": requesting_user_id}))
    granted_item_ids = [g.get("vault_item_id") for g in grants if g.get("vault_item_id")]

    granted_items: list[dict[str, Any]] = []
    for gid in granted_item_ids:
        if gid in owned_ids:
            continue
        granted_doc = _find_by_id("vault_items", str(gid))
        if granted_doc and granted_doc.get("project_id") == project_id:
            if vault_scope is None or granted_doc.get("vault_scope") == vault_scope:
                granted_items.append(granted_doc)

    all_items = owned_items + granted_items
    return [_serialize(doc) for doc in all_items if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Collections
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_collection(payload: VaultCollectionCreate, owner_user_id: str) -> dict[str, Any]:
    col = _col("vault_collections")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "owner_user_id": owner_user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_vault_collections(project_id: str, owner_user_id: str) -> list[dict[str, Any]]:
    col = _col("vault_collections")
    cursor = col.find({"project_id": project_id, "owner_user_id": owner_user_id})
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Access Grants
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_access_grant(
    payload: VaultAccessGrantCreate,
    granting_user_id: str,
) -> dict[str, Any]:
    item = _find_by_id("vault_items", payload.vault_item_id)
    if not item:
        raise ValueError("Vault item not found.")

    owner = _str_id(item.get("owner_user_id") or "")
    if owner != granting_user_id:
        existing_grant = _col("vault_access_grants").find_one({
            "vault_item_id": payload.vault_item_id,
            "grantee_user_id": granting_user_id,
            "permission_role": {"$in": ["steward"]},
        })
        if not existing_grant:
            raise PermissionError("Only the owner or steward can grant access.")

    col = _col("vault_access_grants")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "granted_by_user_id": granting_user_id,
        "created_at": now,
    }
    if payload.expires_at is not None:
        doc["expires_at"] = payload.expires_at.isoformat()
    else:
        doc["expires_at"] = None
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_vault_access_grants(item_id: str, requesting_user_id: str) -> list[dict[str, Any]]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")

    owner = _str_id(item.get("owner_user_id") or "")
    if owner != requesting_user_id:
        raise PermissionError("Only the owner or steward can list grants.")

    col = _col("vault_access_grants")
    cursor = col.find({"vault_item_id": item_id})
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Release Rules
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_release_rule(
    payload: VaultReleaseRuleCreate,
    owner_user_id: str,
) -> dict[str, Any]:
    item = _find_by_id("vault_items", payload.vault_item_id)
    if not item:
        raise ValueError("Vault item not found.")

    owner = _str_id(item.get("owner_user_id") or "")
    if owner != owner_user_id:
        raise PermissionError("Only the owner can create release rules.")

    col = _col("vault_release_rules")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "created_by_user_id": owner_user_id,
        "created_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_vault_release_rules(item_id: str, requesting_user_id: str) -> list[dict[str, Any]]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")

    owner = _str_id(item.get("owner_user_id") or "")
    if owner != requesting_user_id:
        raise PermissionError("Only the owner can view release rules.")

    col = _col("vault_release_rules")
    cursor = col.find({"vault_item_id": item_id})
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Audit Events
# ─────────────────────────────────────────────────────────────────────────────

def log_vault_audit_event(
    item_id: str,
    user_id: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    col = _col("vault_audit_events")
    col.insert_one({
        "vault_item_id": item_id,
        "user_id": user_id,
        "action": action,
        "details": details or {},
        "created_at": _now(),
    })


def list_vault_audit_events(item_id: str, requesting_user_id: str) -> list[dict[str, Any]]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")

    owner = _str_id(item.get("owner_user_id") or "")
    if owner != requesting_user_id:
        # Check executor grant
        grant = _col("vault_access_grants").find_one({
            "vault_item_id": item_id,
            "grantee_user_id": requesting_user_id,
            "permission_role": "executor",
        })
        if not grant:
            raise PermissionError("Only the owner or executor can view audit events.")

    col = _col("vault_audit_events")
    cursor = col.find({"vault_item_id": item_id}).sort("created_at", -1)
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]
