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


def _normalize(value: Any) -> str:
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


def _item_project_id(doc: dict[str, Any]) -> str:
    return _normalize(doc.get("project_id"))


def _assert_authorized_project(
    doc: dict[str, Any],
    *,
    authorized_project_id: str = "",
) -> None:
    normalized_authorized = _normalize(authorized_project_id)
    if not normalized_authorized:
        return
    if _item_project_id(doc) != normalized_authorized:
        raise PermissionError("Vault item does not belong to the active workspace.")


def _parse_iso_datetime(value: Any) -> datetime | None:
    raw = _normalize(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _should_hide_pre_release_item(doc: dict[str, Any], requesting_user_id: str) -> bool:
    owner_user_id = _normalize(doc.get("owner_user_id"))
    if owner_user_id and owner_user_id == _normalize(requesting_user_id):
        return False
    reveal_at = _parse_iso_datetime(doc.get("reveal_at"))
    if reveal_at is None:
        return False
    now = datetime.now(timezone.utc)
    return reveal_at > now


def _resolve_release_fields(
    *,
    reveal_at_iso: str | None,
    release_state: str,
) -> tuple[str, str | None]:
    reveal_at_dt = _parse_iso_datetime(reveal_at_iso)
    normalized_state = _normalize(release_state).lower() or "draft"
    if reveal_at_dt is None:
        if normalized_state == "scheduled":
            normalized_state = "draft"
        return normalized_state, None
    if reveal_at_dt > datetime.now(timezone.utc):
        return "scheduled", reveal_at_dt.isoformat()
    if normalized_state == "draft":
        return "released", reveal_at_dt.isoformat()
    return normalized_state, reveal_at_dt.isoformat()


def _has_grant(
    item_id: str,
    user_id: str,
    *,
    roles: list[str] | None = None,
) -> bool:
    query: dict[str, Any] = {
        "vault_item_id": item_id,
        "grantee_user_id": user_id,
    }
    if roles:
        query["permission_role"] = {"$in": roles}
    grant = _col("vault_access_grants").find_one(query)
    return bool(grant)


# ─────────────────────────────────────────────────────────────────────────────
# Vault Items
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_item(
    payload: VaultItemCreate,
    owner_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    normalized_project_id = _normalize(payload.project_id)
    normalized_authorized_project_id = _normalize(authorized_project_id)
    if normalized_authorized_project_id and normalized_project_id != normalized_authorized_project_id:
        raise PermissionError("Vault item project must match the active workspace.")

    col = _col("vault_items")
    now = _now()
    release_state, reveal_at = _resolve_release_fields(
        reveal_at_iso=payload.reveal_at.isoformat() if payload.reveal_at else None,
        release_state=payload.release_state,
    )
    doc: dict[str, Any] = {
        **payload.model_dump(exclude={"reveal_at", "release_state"}),
        "project_id": normalized_project_id,
        "owner_user_id": owner_user_id,
        "status": "active",
        "release_state": release_state,
        "reveal_at": reveal_at,
        "created_at": now,
        "updated_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    item_id = _str_id(result.inserted_id)
    log_vault_audit_event(
        item_id,
        owner_user_id,
        "create",
        details={
            "project_id": normalized_project_id,
            "release_state": release_state,
            "reveal_at": reveal_at,
        },
    )
    return _serialize(doc) or {}


def get_vault_item(
    item_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any] | None:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        return None
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(doc.get("_id"))
    owner = _normalize(doc.get("owner_user_id"))
    if owner == _normalize(requesting_user_id):
        log_vault_audit_event(canonical_item_id, requesting_user_id, "view")
        return _serialize(doc)

    if _should_hide_pre_release_item(doc, requesting_user_id):
        raise ValueError("Vault item is scheduled and not yet available.")

    if _has_grant(canonical_item_id, requesting_user_id):
        log_vault_audit_event(canonical_item_id, requesting_user_id, "view")
        return _serialize(doc)

    raise ValueError("Access denied.")


def update_vault_item(
    item_id: str,
    updates: VaultItemUpdate,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any] | None:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(doc.get("_id"))
    owner = _normalize(doc.get("owner_user_id"))
    if owner != _normalize(requesting_user_id):
        if not _has_grant(canonical_item_id, requesting_user_id, roles=["steward"]):
            raise PermissionError("Only the owner or steward can update this item.")

    update_data = updates.model_dump(exclude_unset=True, exclude={"reveal_at", "release_state"})
    requested_reveal_at = updates.reveal_at.isoformat() if updates.reveal_at else doc.get("reveal_at")
    requested_release_state = updates.release_state or _normalize(doc.get("release_state")) or "draft"
    release_state, reveal_at = _resolve_release_fields(
        reveal_at_iso=requested_reveal_at,
        release_state=requested_release_state,
    )
    update_data["release_state"] = release_state
    update_data["reveal_at"] = reveal_at
    update_data["updated_at"] = _now()

    col = _col("vault_items")
    if ObjectId.is_valid(item_id):
        col.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})
    else:
        col.update_one({"_id": item_id}, {"$set": update_data})

    updated = _serialize(_find_by_id("vault_items", item_id))
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "update",
        details={
            "fields": sorted(update_data.keys()),
            "release_state": release_state,
            "reveal_at": reveal_at,
        },
    )
    return updated


def delete_vault_item(
    item_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> bool:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    owner = _normalize(doc.get("owner_user_id"))
    if owner != _normalize(requesting_user_id):
        raise PermissionError("Only the owner can delete this item.")

    canonical_item_id = _str_id(doc.get("_id"))
    col = _col("vault_items")
    if ObjectId.is_valid(item_id):
        col.delete_one({"_id": ObjectId(item_id)})
    else:
        col.delete_one({"_id": item_id})

    log_vault_audit_event(canonical_item_id, requesting_user_id, "delete")
    return True


def list_vault_items(
    project_id: str,
    requesting_user_id: str,
    vault_scope: str | None = None,
    *,
    authorized_project_id: str = "",
) -> list[dict[str, Any]]:
    normalized_project_id = _normalize(project_id)
    normalized_authorized_project_id = _normalize(authorized_project_id)
    if normalized_authorized_project_id and normalized_project_id != normalized_authorized_project_id:
        raise PermissionError("Requested project does not match the active workspace.")

    col = _col("vault_items")

    owned_query: dict[str, Any] = {
        "owner_user_id": requesting_user_id,
        "project_id": normalized_project_id,
    }
    if vault_scope:
        owned_query["vault_scope"] = vault_scope
    owned_items = list(col.find(owned_query))

    owned_ids = {_str_id(doc.get("_id")) for doc in owned_items}
    grants = list(_col("vault_access_grants").find({"grantee_user_id": requesting_user_id}))
    granted_item_ids = [_normalize(g.get("vault_item_id")) for g in grants if _normalize(g.get("vault_item_id"))]

    granted_items: list[dict[str, Any]] = []
    for gid in granted_item_ids:
        if gid in owned_ids:
            continue
        granted_doc = _find_by_id("vault_items", gid)
        if not granted_doc:
            continue
        if _item_project_id(granted_doc) != normalized_project_id:
            continue
        if _should_hide_pre_release_item(granted_doc, requesting_user_id):
            continue
        if vault_scope is None or granted_doc.get("vault_scope") == vault_scope:
            granted_items.append(granted_doc)

    all_items = owned_items + granted_items
    return [_serialize(doc) for doc in all_items if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Collections
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_collection(
    payload: VaultCollectionCreate,
    owner_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    normalized_project_id = _normalize(payload.project_id)
    normalized_authorized_project_id = _normalize(authorized_project_id)
    if normalized_authorized_project_id and normalized_project_id != normalized_authorized_project_id:
        raise PermissionError("Vault collection project must match the active workspace.")

    col = _col("vault_collections")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "project_id": normalized_project_id,
        "owner_user_id": owner_user_id,
        "created_at": now,
        "updated_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_vault_collections(
    project_id: str,
    owner_user_id: str,
    *,
    authorized_project_id: str = "",
) -> list[dict[str, Any]]:
    normalized_project_id = _normalize(project_id)
    normalized_authorized_project_id = _normalize(authorized_project_id)
    if normalized_authorized_project_id and normalized_project_id != normalized_authorized_project_id:
        raise PermissionError("Requested project does not match the active workspace.")

    col = _col("vault_collections")
    cursor = col.find({"project_id": normalized_project_id, "owner_user_id": owner_user_id})
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Access Grants
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_access_grant(
    payload: VaultAccessGrantCreate,
    granting_user_id: str,
    *,
    item_id: str = "",
    authorized_project_id: str = "",
) -> dict[str, Any]:
    target_item_id = _normalize(item_id) or _normalize(payload.vault_item_id)
    item = _find_by_id("vault_items", target_item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(item.get("_id"))
    owner = _normalize(item.get("owner_user_id"))
    if owner != _normalize(granting_user_id):
        if not _has_grant(canonical_item_id, granting_user_id, roles=["steward"]):
            raise PermissionError("Only the owner or steward can grant access.")

    grantee_project_id = _normalize(payload.grantee_project_id)
    if grantee_project_id and grantee_project_id != _item_project_id(item):
        raise PermissionError("Cross-project vault grants are not allowed.")

    col = _col("vault_access_grants")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "vault_item_id": canonical_item_id,
        "grantee_project_id": grantee_project_id or None,
        "granted_by_user_id": granting_user_id,
        "created_at": now,
    }
    if payload.expires_at is not None:
        doc["expires_at"] = payload.expires_at.isoformat()
    else:
        doc["expires_at"] = None
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    log_vault_audit_event(
        canonical_item_id,
        granting_user_id,
        "grant_access",
        details={
            "grantee_user_id": _normalize(payload.grantee_user_id) or None,
            "grantee_project_id": grantee_project_id or None,
            "permission_role": _normalize(payload.permission_role) or "viewer",
        },
    )
    return _serialize(doc) or {}


def list_vault_access_grants(
    item_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> list[dict[str, Any]]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(item.get("_id"))
    owner = _normalize(item.get("owner_user_id"))
    if owner != _normalize(requesting_user_id) and not _has_grant(
        canonical_item_id,
        requesting_user_id,
        roles=["steward"],
    ):
        raise PermissionError("Only the owner or steward can list grants.")

    col = _col("vault_access_grants")
    cursor = col.find({"vault_item_id": canonical_item_id})
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Vault Release Rules
# ─────────────────────────────────────────────────────────────────────────────

def create_vault_release_rule(
    payload: VaultReleaseRuleCreate,
    owner_user_id: str,
    *,
    item_id: str = "",
    authorized_project_id: str = "",
) -> dict[str, Any]:
    target_item_id = _normalize(item_id) or _normalize(payload.vault_item_id)
    item = _find_by_id("vault_items", target_item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(item.get("_id"))
    owner = _normalize(item.get("owner_user_id"))
    if owner != _normalize(owner_user_id):
        raise PermissionError("Only the owner can create release rules.")

    col = _col("vault_release_rules")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "vault_item_id": canonical_item_id,
        "created_by_user_id": owner_user_id,
        "created_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    log_vault_audit_event(
        canonical_item_id,
        owner_user_id,
        "create_release_rule",
        details={
            "trigger_type": _normalize(payload.trigger_type),
            "release_to": _normalize(payload.release_to),
        },
    )
    return _serialize(doc) or {}


def list_vault_release_rules(
    item_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> list[dict[str, Any]]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(item.get("_id"))
    owner = _normalize(item.get("owner_user_id"))
    if owner != _normalize(requesting_user_id):
        raise PermissionError("Only the owner can view release rules.")

    col = _col("vault_release_rules")
    cursor = col.find({"vault_item_id": canonical_item_id})
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


def list_vault_audit_events(
    item_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> list[dict[str, Any]]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)

    canonical_item_id = _str_id(item.get("_id"))
    owner = _normalize(item.get("owner_user_id"))
    if owner != _normalize(requesting_user_id):
        grant = _col("vault_access_grants").find_one({
            "vault_item_id": canonical_item_id,
            "grantee_user_id": requesting_user_id,
            "permission_role": "executor",
        })
        if not grant:
            raise PermissionError("Only the owner or executor can view audit events.")

    col = _col("vault_audit_events")
    cursor = col.find({"vault_item_id": canonical_item_id}).sort("created_at", -1)
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]
