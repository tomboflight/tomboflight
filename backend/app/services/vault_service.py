from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, cast

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database
from app.schemas.vault import (
    VaultAccessGrantCreate,
    VaultAccessGrantUpdate,
    VaultCollectionCreate,
    VaultItemCreate,
    VaultItemUpdate,
    VaultReleaseRuleCreate,
    VaultReleaseRuleUpdate,
)


ACTIVE_ITEM_STATUSES = {"", "active"}
INACTIVE_ITEM_STATUSES = {"closed", "deleted", "revoked", "disabled"}
ACTIVE_GRANT_STATUSES = {"", "active"}
INACTIVE_GRANT_STATUSES = {"revoked", "deleted", "expired", "disabled"}
HOUSEHOLD_ADMIN_ROLES = {"billing_owner", "co_owner", "family_manager"}
WORKSPACE_READ_ROLES = {
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
    "viewer",
    "minor_viewer",
    "linked_relative",
    "legacy_executor",
}
ACTIVE_LINK_STATUSES = {"active", "accepted", "approved", "verified", "linked"}


def _col(name: str) -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db[name])


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _str_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return str(value or "").strip()


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _id_queries(item_id: str) -> list[dict[str, Any]]:
    normalized = _normalize(item_id)
    if not normalized:
        return []
    queries: list[dict[str, Any]] = []
    if ObjectId.is_valid(normalized):
        queries.append({"_id": ObjectId(normalized)})
    queries.append({"_id": normalized})
    return queries


def _find_by_id(collection_name: str, item_id: str) -> dict[str, Any] | None:
    col = _col(collection_name)
    for query in _id_queries(item_id):
        doc = col.find_one(query)
        if doc:
            return cast(dict[str, Any], doc)
    return None


def _update_by_id(collection_name: str, item_id: str, fields: dict[str, Any]) -> None:
    existing = _find_by_id(collection_name, item_id)
    if existing:
        _col(collection_name).update_one({"_id": existing.get("_id")}, {"$set": fields})


def _delete_by_id(collection_name: str, item_id: str) -> None:
    existing = _find_by_id(collection_name, item_id)
    if existing:
        _col(collection_name).delete_one({"_id": existing.get("_id")})


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
    if normalized_authorized and _item_project_id(doc) != normalized_authorized:
        raise PermissionError("Vault item does not belong to the active workspace.")


def _parse_iso_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
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


def _is_item_operable(doc: dict[str, Any]) -> bool:
    status = _normalize(doc.get("status")).lower()
    if status in INACTIVE_ITEM_STATUSES or status not in ACTIVE_ITEM_STATUSES:
        return False
    return not (
        doc.get("access_enabled") is False
        or bool(doc.get("owner_account_deleted"))
    )


def _assert_item_operable(doc: dict[str, Any]) -> None:
    if not _is_item_operable(doc):
        raise ValueError("Vault item is not available.")


def _is_grant_active(grant: dict[str, Any], *, now: datetime | None = None) -> bool:
    status = _normalize(grant.get("status")).lower()
    if status in INACTIVE_GRANT_STATUSES or status not in ACTIVE_GRANT_STATUSES:
        return False
    if grant.get("access_enabled") is False:
        return False
    expires_raw = grant.get("expires_at")
    if expires_raw not in (None, ""):
        expires_at = _parse_iso_datetime(expires_raw)
        if expires_at is None or expires_at <= (now or _now_dt()):
            return False
    return True


def _grant_targets_requester(
    grant: dict[str, Any],
    *,
    user_id: str,
    project_id: str = "",
) -> bool:
    grantee_user_id = _normalize(grant.get("grantee_user_id"))
    if grantee_user_id:
        return grantee_user_id == _normalize(user_id)
    grantee_project_id = _normalize(grant.get("grantee_project_id"))
    return bool(grantee_project_id and grantee_project_id == _normalize(project_id))


def _active_grants_for(
    item_id: str,
    user_id: str,
    *,
    project_id: str = "",
) -> list[dict[str, Any]]:
    now = _now_dt()
    grants: list[dict[str, Any]] = []
    for raw_grant in _col("vault_access_grants").find({"vault_item_id": item_id}):
        grant = cast(dict[str, Any], raw_grant)
        if _is_grant_active(grant, now=now) and _grant_targets_requester(
            grant,
            user_id=user_id,
            project_id=project_id,
        ):
            grants.append(grant)
    return grants


def _has_grant(
    item_id: str,
    user_id: str,
    *,
    roles: Iterable[str] | None = None,
    project_id: str = "",
) -> bool:
    normalized_roles = {_normalize(role).lower() for role in roles or [] if _normalize(role)}
    grants = _active_grants_for(item_id, user_id, project_id=project_id)
    if not normalized_roles:
        return bool(grants)
    return any(_normalize(grant.get("permission_role")).lower() in normalized_roles for grant in grants)


def _active_release_rules(item_id: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for raw_rule in _col("vault_release_rules").find({"vault_item_id": item_id}):
        rule = cast(dict[str, Any], raw_rule)
        status = _normalize(rule.get("status")).lower()
        if status not in {"revoked", "deleted"} and rule.get("access_enabled") is not False:
            rules.append(rule)
    return rules


def _release_state_for_doc(
    doc: dict[str, Any],
    *,
    rules: Iterable[dict[str, Any]] | None = None,
) -> str:
    """Return a migration-safe declared release state.

    Phase-22 and newer records always persist ``release_state``. Older Vault
    records did not, so an absent value cannot safely mean draft: doing that
    would silently remove previously shared household records from accepted
    co-owners. Legacy timing or rule data is still treated as governed and
    fail-closed; only an otherwise ordinary legacy record is treated as
    released. Privacy checks remain independent and authoritative.
    """

    explicit_state = _normalize(doc.get("release_state")).lower()
    if explicit_state:
        return explicit_state
    active_rules = (
        list(rules)
        if rules is not None
        else _active_release_rules(_str_id(doc.get("_id")))
    )
    if _normalize(doc.get("reveal_at")) or active_rules:
        return "scheduled"
    return "released"


def _rule_condition_satisfied(rule: dict[str, Any], *, now: datetime) -> bool:
    status = _normalize(rule.get("status")).lower()
    trigger_type = _normalize(rule.get("trigger_type")).lower()
    if status not in {"", "active", "satisfied"}:
        return False
    if trigger_type == "on_date":
        trigger_at = _parse_iso_datetime(rule.get("trigger_value"))
        return bool(trigger_at and trigger_at <= now)
    if status == "satisfied":
        trustee_id = _normalize(rule.get("trustee_user_id"))
        return bool(
            trustee_id
            and _normalize(rule.get("satisfied_by_user_id")) == trustee_id
        )
    # Non-date rules require a governed update to status=satisfied. Unknown
    # trigger types also remain locked, which is the safe migration behavior.
    return False


def _rule_audience_allows(
    rule: dict[str, Any],
    *,
    user_id: str,
    workspace_role: str,
    relationship_scope: str,
    link_status: str,
) -> bool:
    audience = _normalize(rule.get("release_to")).lower() or "descendants"
    role = _normalize(workspace_role).lower()
    relationship = _normalize(relationship_scope).lower()
    active_link = _normalize(link_status).lower() in ACTIVE_LINK_STATUSES
    named = {_normalize(value) for value in rule.get("named_recipients") or [] if _normalize(value)}
    if audience == "named_list":
        return _normalize(user_id) in named
    if audience == "descendants":
        return any(token in relationship for token in ("descendant", "child", "grandchild"))
    if audience == "spouse":
        return (
            role == "co_owner" and active_link
        ) or any(token in relationship for token in ("spouse", "partner"))
    if audience == "household":
        return role in WORKSPACE_READ_ROLES and role != "linked_relative"
    if audience == "all_linked":
        return role in WORKSPACE_READ_ROLES and active_link
    return audience == "public"


def _has_household_admin_access(role: str, link_status: str) -> bool:
    normalized_role = _normalize(role).lower()
    if normalized_role in {"billing_owner", "family_manager"}:
        return True
    return (
        normalized_role == "co_owner"
        and _normalize(link_status).lower() in ACTIVE_LINK_STATUSES
    )


def _has_owner_and_co_owner_access(role: str, link_status: str) -> bool:
    normalized_role = _normalize(role).lower()
    if normalized_role == "billing_owner":
        return True
    return (
        normalized_role == "co_owner"
        and _normalize(link_status).lower() in ACTIVE_LINK_STATUSES
    )


def _release_allows(
    doc: dict[str, Any],
    *,
    user_id: str,
    workspace_role: str = "",
    relationship_scope: str = "",
    link_status: str = "",
) -> bool:
    now = _now_dt()
    rules = _active_release_rules(_str_id(doc.get("_id")))
    state = _release_state_for_doc(doc, rules=rules)
    reveal_at = _parse_iso_datetime(doc.get("reveal_at"))
    if _normalize(doc.get("reveal_at")) and reveal_at is None:
        return False
    if reveal_at is not None and reveal_at > now:
        return False
    if state == "released":
        base_released = True
    elif state == "scheduled":
        base_released = bool((reveal_at and reveal_at <= now) or rules)
    else:
        base_released = False
    if not base_released:
        return False
    if not rules:
        return True
    return all(
        _rule_condition_satisfied(rule, now=now)
        and _rule_audience_allows(
            rule,
            user_id=user_id,
            workspace_role=workspace_role,
            relationship_scope=relationship_scope,
            link_status=link_status,
        )
        for rule in rules
    )


def _privacy_allows(
    doc: dict[str, Any],
    *,
    user_id: str,
    workspace_role: str = "",
    link_status: str = "",
) -> bool:
    item_id = _str_id(doc.get("_id"))
    has_grant = _has_grant(item_id, user_id, project_id=_item_project_id(doc))
    named_by_rule = any(
        _normalize(rule.get("release_to")).lower() == "named_list"
        and _normalize(user_id)
        in {_normalize(value) for value in rule.get("named_recipients") or [] if _normalize(value)}
        for rule in _active_release_rules(item_id)
    )
    raw_privacy = doc.get("privacy")
    if raw_privacy is None:
        return has_grant  # migration compatibility for pre-privacy records
    privacy = _normalize(raw_privacy).lower()
    role = _normalize(workspace_role).lower()
    if privacy == "private_owner":
        return False
    if privacy == "owner_and_co_owner":
        return _has_owner_and_co_owner_access(role, link_status)
    if privacy == "selected_relatives":
        return has_grant or named_by_rule
    if privacy == "household_admins":
        return has_grant or _has_household_admin_access(role, link_status)
    if privacy == "all_linked":
        return has_grant or (
            role in WORKSPACE_READ_ROLES
            and _normalize(link_status).lower() in ACTIVE_LINK_STATUSES
        )
    return privacy == "public_memorial"


def _asset_access(doc: dict[str, Any]) -> dict[str, Any]:
    upload_id = _normalize(doc.get("current_upload_id") or doc.get("upload_id"))
    if not upload_id:
        return {
            "linked": False,
            "available": False,
            "blocked_reason": "not_linked",
            "current_upload_id": None,
            "version": None,
        }
    upload = _find_by_id("uploaded_files", upload_id)
    reason: str | None = None
    if upload is None:
        reason = "upload_missing"
    elif _normalize(upload.get("vault_item_id")) != _str_id(doc.get("_id")):
        reason = "linkage_mismatch"
    elif _normalize(upload.get("project_id")) != _item_project_id(doc):
        reason = "workspace_linkage_mismatch"
    elif (
        _normalize(doc.get("family_id"))
        and _normalize(upload.get("family_id")) != _normalize(doc.get("family_id"))
    ):
        reason = "family_linkage_mismatch"
    elif (
        _normalize(doc.get("member_id"))
        and _normalize(upload.get("member_id")) != _normalize(doc.get("member_id"))
    ):
        reason = "member_linkage_mismatch"
    elif bool(upload.get("quarantined")):
        reason = "security_quarantine"
    elif _normalize(upload.get("scan_status")).lower() != "clean":
        reason = "security_scan_not_clean"
    elif _normalize(upload.get("deletion_status")).lower() in {"pending", "failed", "deleted"}:
        reason = "asset_deletion_state"
    elif _normalize(upload.get("vault_version_deletion_status")).lower() == "deleted":
        reason = "asset_deletion_state"
    elif _normalize(upload.get("replacement_status")).lower() == "deleted":
        reason = "asset_deletion_state"
    elif upload.get("account_access_enabled") is False or bool(upload.get("owner_account_deleted")):
        reason = "asset_access_disabled"
    return {
        "linked": True,
        "available": reason is None,
        "blocked_reason": reason,
        "current_upload_id": upload_id,
        "version": int(doc.get("asset_version") or 1),
    }


def _serialize_item(doc: dict[str, Any]) -> dict[str, Any]:
    result = _serialize(doc) or {}
    reveal_at = _parse_iso_datetime(doc.get("reveal_at"))
    rules = _active_release_rules(_str_id(doc.get("_id")))
    state = _release_state_for_doc(doc, rules=rules)
    conditions_satisfied = all(_rule_condition_satisfied(rule, now=_now_dt()) for rule in rules)
    if state == "scheduled" and (reveal_at is not None or rules):
        result["effective_release_state"] = (
            "released"
            if (reveal_at is None or reveal_at <= _now_dt()) and conditions_satisfied
            else "scheduled"
        )
    else:
        result["effective_release_state"] = state
    result["asset_access"] = _asset_access(doc)
    return result


def _resolve_release_fields(
    *,
    reveal_at_iso: str | None,
    release_state: str,
) -> tuple[str, str | None]:
    reveal_at_dt = _parse_iso_datetime(reveal_at_iso)
    normalized_state = _normalize(release_state).lower() or "draft"
    if normalized_state not in {"draft", "scheduled", "released"}:
        raise ValueError("Invalid release_state.")
    if normalized_state == "scheduled" and reveal_at_dt is None:
        raise ValueError("Scheduled vault items require reveal_at or an active release rule.")
    if reveal_at_iso and reveal_at_dt is None:
        raise ValueError("reveal_at must be a valid ISO-8601 datetime.")
    if reveal_at_dt is not None:
        if reveal_at_dt > _now_dt():
            normalized_state = "scheduled"
        elif normalized_state == "scheduled":
            normalized_state = "released"
    return normalized_state, reveal_at_dt.isoformat() if reveal_at_dt else None


def _validate_reference(
    collection_name: str,
    reference_id: str,
    *,
    label: str,
) -> dict[str, Any]:
    doc = _find_by_id(collection_name, reference_id)
    if not doc:
        raise ValueError(f"{label} not found.")
    return doc


def _validate_item_references(
    *,
    project_id: str,
    owner_user_id: str,
    vault_scope: str = "",
    family_id: str = "",
    member_id: str = "",
    collection_id: str = "",
) -> None:
    if _normalize(vault_scope).lower() == "organization" and (family_id or member_id):
        raise ValueError("Organization vault items cannot reference a family or family member.")
    if family_id:
        family = _validate_reference("families", family_id, label="Vault family")
        if _normalize(family.get("project_id")) not in {"", project_id}:
            raise PermissionError("Vault family does not belong to the active workspace.")
    if member_id:
        member = _validate_reference("family_members", member_id, label="Vault family member")
        member_family_id = _normalize(member.get("family_id"))
        if family_id and member_family_id != family_id:
            raise PermissionError("Vault family member does not belong to the selected family.")
        if not family_id and member_family_id:
            member_family = _validate_reference("families", member_family_id, label="Vault member family")
            if _normalize(member_family.get("project_id")) not in {"", project_id}:
                raise PermissionError("Vault family member does not belong to the active workspace.")
    if collection_id:
        collection = _validate_reference("vault_collections", collection_id, label="Vault collection")
        if _normalize(collection.get("project_id")) != project_id:
            raise PermissionError("Vault collection does not belong to the active workspace.")
        if collection.get("access_enabled") is False or _normalize(collection.get("status")).lower() in {
            "closed",
            "deleted",
        }:
            raise ValueError("Vault collection is not available.")
        if (
            _normalize(collection.get("privacy")).lower() == "private_owner"
            and _normalize(collection.get("owner_user_id")) != owner_user_id
        ):
            raise PermissionError("Owner-only collections cannot receive another owner's item.")


def _validate_user_reference(user_id: str, *, label: str) -> None:
    if not _normalize(user_id) or not _find_by_id("users", user_id):
        raise ValueError(f"{label} not found.")


def _can_manage_item(doc: dict[str, Any], user_id: str, *, roles: Iterable[str]) -> bool:
    if _normalize(doc.get("owner_user_id")) == _normalize(user_id):
        return True
    if _normalize(doc.get("privacy")).lower() in {"private_owner", "owner_and_co_owner"}:
        return False
    return _has_grant(
        _str_id(doc.get("_id")),
        user_id,
        roles=roles,
        project_id=_item_project_id(doc),
    )


# Vault items

def create_vault_item(
    payload: VaultItemCreate,
    owner_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    project_id = _normalize(payload.project_id)
    if _normalize(authorized_project_id) and project_id != _normalize(authorized_project_id):
        raise PermissionError("Vault item project must match the active workspace.")
    _validate_item_references(
        project_id=project_id,
        owner_user_id=_normalize(owner_user_id),
        vault_scope=payload.vault_scope,
        family_id=_normalize(payload.family_id),
        member_id=_normalize(payload.member_id),
        collection_id=_normalize(payload.collection_id),
    )
    release_state, reveal_at = _resolve_release_fields(
        reveal_at_iso=payload.reveal_at.isoformat() if payload.reveal_at else None,
        release_state=payload.release_state,
    )
    initial_upload_id = _normalize(payload.current_upload_id or payload.upload_id)
    if initial_upload_id:
        upload = _validate_reference("uploaded_files", initial_upload_id, label="Vault upload")
        if _normalize(upload.get("project_id")) != project_id:
            raise PermissionError("Vault upload does not belong to the active workspace.")
        if _normalize(upload.get("uploaded_by_user_id")) not in {"", _normalize(owner_user_id)}:
            raise PermissionError("Vault upload does not belong to the item owner.")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(exclude={"reveal_at", "release_state", "upload_id", "current_upload_id"}),
        "project_id": project_id,
        "owner_user_id": _normalize(owner_user_id),
        "status": "active",
        "access_enabled": True,
        "release_state": release_state,
        "reveal_at": reveal_at,
        "asset_versions": [],
        "created_at": now,
        "updated_at": now,
    }
    result = _col("vault_items").insert_one(doc)
    doc["_id"] = result.inserted_id
    item_id = _str_id(result.inserted_id)
    log_vault_audit_event(
        item_id,
        owner_user_id,
        "create",
        details={"project_id": project_id, "release_state": release_state, "reveal_at": reveal_at},
    )
    if initial_upload_id:
        try:
            return link_vault_upload(
                item_id,
                initial_upload_id,
                owner_user_id,
                authorized_project_id=project_id,
                family_id=_normalize(payload.family_id),
                member_id=_normalize(payload.member_id),
                version=1,
            )
        except Exception:
            _delete_by_id("vault_items", item_id)
            raise
    return _serialize_item(doc)


def get_vault_item(
    item_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
    requesting_workspace_role: str = "",
    relationship_scope: str = "",
    link_status: str = "",
) -> dict[str, Any] | None:
    doc = _find_by_id("vault_items", item_id)
    if not doc:
        return None
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)
    _assert_item_operable(doc)
    is_owner = _normalize(doc.get("owner_user_id")) == _normalize(requesting_user_id)
    if not is_owner:
        if not _privacy_allows(
            doc,
            user_id=requesting_user_id,
            workspace_role=requesting_workspace_role,
            link_status=link_status,
        ):
            raise ValueError("Access denied.")
        if not _release_allows(
            doc,
            user_id=requesting_user_id,
            workspace_role=requesting_workspace_role,
            relationship_scope=relationship_scope,
            link_status=link_status,
        ):
            raise ValueError("Vault item is not released to this user.")
        asset = _asset_access(doc)
        if asset["linked"] and not asset["available"]:
            raise ValueError("Vault asset is not available.")
    canonical_item_id = _str_id(doc.get("_id"))
    log_vault_audit_event(canonical_item_id, requesting_user_id, "view")
    return _serialize_item(doc)


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
    _assert_item_operable(doc)
    canonical_item_id = _str_id(doc.get("_id"))
    is_owner = _normalize(doc.get("owner_user_id")) == _normalize(requesting_user_id)
    is_steward = _has_grant(
        canonical_item_id,
        requesting_user_id,
        roles=("steward",),
        project_id=_item_project_id(doc),
    )
    is_editor = _has_grant(
        canonical_item_id,
        requesting_user_id,
        roles=("editor",),
        project_id=_item_project_id(doc),
    )
    if not is_owner and (
        _normalize(doc.get("privacy")).lower() in {"private_owner", "owner_and_co_owner"}
        or not (is_steward or is_editor)
    ):
        raise PermissionError("Only the owner, steward, or editor can update this item.")
    requested_fields = set(updates.model_fields_set)
    owner_only_fields = {"family_id", "member_id", "vault_scope", "privacy", "release_state", "reveal_at"}
    if not is_owner and requested_fields & owner_only_fields:
        raise PermissionError("Only the owner can change vault scope, privacy, references, or release timing.")
    if not is_owner and is_editor and not is_steward:
        editor_fields = {"title", "description", "collection_id", "tags", "metadata"}
        if requested_fields - editor_fields:
            raise PermissionError("Editors can only update item content and organization fields.")
    _validate_item_references(
        project_id=_item_project_id(doc),
        owner_user_id=_normalize(doc.get("owner_user_id")),
        vault_scope=updates.vault_scope if "vault_scope" in requested_fields else _normalize(doc.get("vault_scope")),
        family_id=_normalize(updates.family_id if "family_id" in requested_fields else doc.get("family_id")),
        member_id=_normalize(updates.member_id if "member_id" in requested_fields else doc.get("member_id")),
        collection_id=_normalize(
            updates.collection_id if "collection_id" in requested_fields else doc.get("collection_id")
        ),
    )
    update_data = updates.model_dump(exclude_unset=True, exclude={"reveal_at", "release_state"})
    requested_reveal_at = (
        updates.reveal_at.isoformat() if updates.reveal_at else None
    ) if "reveal_at" in requested_fields else doc.get("reveal_at")
    requested_release_state = (
        updates.release_state
        if "release_state" in requested_fields
        else _release_state_for_doc(doc)
    )
    if requested_release_state == "scheduled" and not requested_reveal_at:
        if not _active_release_rules(canonical_item_id):
            raise ValueError("Scheduled vault items require reveal_at or an active release rule.")
        release_state, reveal_at = "scheduled", None
    else:
        release_state, reveal_at = _resolve_release_fields(
            reveal_at_iso=requested_reveal_at,
            release_state=requested_release_state,
        )
    update_data.update({"release_state": release_state, "reveal_at": reveal_at, "updated_at": _now()})
    _update_by_id("vault_items", canonical_item_id, update_data)
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "update",
        details={"fields": sorted(update_data), "release_state": release_state, "reveal_at": reveal_at},
    )
    updated = _find_by_id("vault_items", canonical_item_id)
    return _serialize_item(updated) if updated else None


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
    _assert_item_operable(doc)
    if _normalize(doc.get("owner_user_id")) != _normalize(requesting_user_id):
        raise PermissionError("Only the owner can delete this item.")
    canonical_item_id = _str_id(doc.get("_id"))
    now = _now()
    _update_by_id(
        "vault_items",
        canonical_item_id,
        {
            "status": "deleted",
            "access_enabled": False,
            "deleted_at": now,
            "deleted_by_user_id": requesting_user_id,
            "updated_at": now,
        },
    )
    for collection_name in ("vault_access_grants", "vault_release_rules"):
        for linked_doc in list(_col(collection_name).find({"vault_item_id": canonical_item_id})):
            _update_by_id(
                collection_name,
                _str_id(linked_doc.get("_id")),
                {
                    "status": "revoked",
                    "access_enabled": False,
                    "revoked_at": now,
                    "revoked_by_user_id": requesting_user_id,
                    "updated_at": now,
                },
            )
    log_vault_audit_event(canonical_item_id, requesting_user_id, "delete")
    return True


def list_vault_items(
    project_id: str,
    requesting_user_id: str,
    vault_scope: str | None = None,
    *,
    authorized_project_id: str = "",
    requesting_workspace_role: str = "",
    relationship_scope: str = "",
    link_status: str = "",
    allowed_vault_scopes: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    project_id = _normalize(project_id)
    if _normalize(authorized_project_id) and project_id != _normalize(authorized_project_id):
        raise PermissionError("Requested project does not match the active workspace.")
    query: dict[str, Any] = {"project_id": project_id}
    if vault_scope:
        query["vault_scope"] = vault_scope
    visible: list[dict[str, Any]] = []
    allowed_scopes = (
        {
            _normalize(scope).lower()
            for scope in allowed_vault_scopes
            if _normalize(scope)
        }
        if allowed_vault_scopes is not None
        else None
    )
    for raw_doc in _col("vault_items").find(query):
        doc = cast(dict[str, Any], raw_doc)
        if allowed_scopes is not None and _normalize(doc.get("vault_scope")).lower() not in allowed_scopes:
            continue
        if not _is_item_operable(doc):
            continue
        if _normalize(doc.get("owner_user_id")) == _normalize(requesting_user_id):
            visible.append(doc)
            continue
        if not _release_allows(
            doc,
            user_id=requesting_user_id,
            workspace_role=requesting_workspace_role,
            relationship_scope=relationship_scope,
            link_status=link_status,
        ):
            continue
        if not _privacy_allows(
            doc,
            user_id=requesting_user_id,
            workspace_role=requesting_workspace_role,
            link_status=link_status,
        ):
            continue
        asset = _asset_access(doc)
        if not asset["linked"] or asset["available"]:
            visible.append(doc)
    visible.sort(key=lambda value: _normalize(value.get("updated_at") or value.get("created_at")), reverse=True)
    return [_serialize_item(doc) for doc in visible]


# Upload linkage and versions

def _validate_upload_for_item(
    item: dict[str, Any],
    upload: dict[str, Any],
    *,
    requesting_user_id: str,
    family_id: str = "",
    member_id: str = "",
) -> None:
    if _normalize(upload.get("project_id")) != _item_project_id(item):
        raise PermissionError("Vault upload does not belong to the item's workspace.")
    requested_family = _normalize(family_id)
    requested_member = _normalize(member_id)
    upload_family = _normalize(upload.get("family_id"))
    upload_member = _normalize(upload.get("member_id"))
    item_family = _normalize(item.get("family_id"))
    item_member = _normalize(item.get("member_id"))
    if _normalize(item.get("vault_scope")).lower() == "organization" and (upload_family or upload_member):
        raise ValueError("Organization vault uploads cannot reference a family or family member.")
    if requested_family and upload_family != requested_family:
        raise PermissionError("Vault upload family does not match the requested family.")
    if requested_member and upload_member != requested_member:
        raise PermissionError("Vault upload member does not match the requested member.")
    if item_family and upload_family and item_family != upload_family:
        raise PermissionError("Vault upload does not belong to the item's family.")
    if item_member and upload_member and item_member != upload_member:
        raise PermissionError("Vault upload does not belong to the item's family member.")
    uploader = _normalize(upload.get("uploaded_by_user_id"))
    if uploader and uploader != _normalize(requesting_user_id):
        raise PermissionError("Only the upload owner can link this asset.")
    if bool(upload.get("quarantined")):
        raise ValueError("Quarantined uploads cannot be linked to a vault item.")
    scan_status = _normalize(upload.get("scan_status")).lower()
    if scan_status and scan_status not in {"pending", "clean"}:
        raise ValueError("Only pending or clean uploads can be linked to a vault item.")
    if upload.get("account_access_enabled") is False or bool(upload.get("owner_account_deleted")):
        raise ValueError("This upload is not available for vault access.")


def link_vault_upload(
    vault_item_id: str,
    upload_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
    family_id: str = "",
    member_id: str = "",
    version: int = 1,
    replaces_upload_id: str = "",
    workspace_member_role: str = "",
) -> dict[str, Any]:
    item = _find_by_id("vault_items", vault_item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    role = _normalize(workspace_member_role).lower()
    item_privacy = _normalize(item.get("privacy")).lower()
    shared_item = item_privacy in {
        "owner_and_co_owner",
        "household_admins",
        "all_linked",
        "public_memorial",
    }
    workspace_role_can_link = (
        role in {"billing_owner", "co_owner"}
        if item_privacy == "owner_and_co_owner"
        else role in HOUSEHOLD_ADMIN_ROLES
    )
    if not _can_manage_item(item, requesting_user_id, roles=("steward", "editor")) and not (
        workspace_role_can_link and shared_item
    ):
        raise PermissionError("Only the owner, steward, or editor can link a vault upload.")
    canonical_item_id = _str_id(item.get("_id"))
    canonical_upload_id = _normalize(upload_id)
    upload = _find_by_id("uploaded_files", canonical_upload_id)
    if not upload:
        raise ValueError("Vault upload not found.")
    if (
        _normalize(item.get("owner_user_id")) != _normalize(requesting_user_id)
        and _vault_privacy_for_upload(upload) == "private_owner"
    ):
        raise PermissionError("Owner-only uploads cannot be linked by another workspace member.")
    _validate_upload_for_item(
        item,
        upload,
        requesting_user_id=requesting_user_id,
        family_id=family_id,
        member_id=member_id,
    )
    linked_item_id = _normalize(upload.get("vault_item_id"))
    if linked_item_id and linked_item_id != canonical_item_id:
        raise PermissionError("This upload is already linked to another vault item.")

    versions = [dict(value) for value in item.get("asset_versions") or [] if isinstance(value, dict)]
    if any(_normalize(entry.get("upload_id")) == canonical_upload_id for entry in versions):
        return _serialize_item(item)
    current_upload_id = _normalize(item.get("current_upload_id") or item.get("upload_id"))
    current_version = int(item.get("asset_version") or 0)
    normalized_replaces = _normalize(replaces_upload_id)
    if current_upload_id:
        if not normalized_replaces:
            raise ValueError("Replacing an existing vault asset requires replaces_upload_id.")
        if normalized_replaces != current_upload_id:
            raise ValueError("replaces_upload_id is stale or does not match the current upload.")
        next_version = current_version + 1
        if version not in {1, next_version}:
            raise ValueError(f"Vault asset version must be {next_version}.")
    else:
        if normalized_replaces:
            raise ValueError("The first vault asset cannot replace another upload.")
        next_version = max(int(version), 1)
        if next_version != 1:
            raise ValueError("The first vault asset must use version 1.")

    now = _now()
    versions.append({
        "version": next_version,
        "upload_id": canonical_upload_id,
        "replaces_upload_id": normalized_replaces or None,
        "original_filename": _normalize(upload.get("original_filename")) or None,
        "content_type": _normalize(upload.get("content_type")) or None,
        "size_bytes": upload.get("size_bytes"),
        "scan_status": _normalize(upload.get("scan_status")).lower() or "pending",
        "created_at": now,
        "created_by_user_id": _normalize(requesting_user_id),
    })
    item_fields: dict[str, Any] = {
        "upload_id": canonical_upload_id,
        "current_upload_id": canonical_upload_id,
        "asset_version": next_version,
        "asset_versions": versions,
        "updated_at": now,
    }
    if not _normalize(item.get("family_id")) and _normalize(upload.get("family_id")):
        item_fields["family_id"] = _normalize(upload.get("family_id"))
    if not _normalize(item.get("member_id")) and _normalize(upload.get("member_id")):
        item_fields["member_id"] = _normalize(upload.get("member_id"))
    if current_upload_id:
        current_field = "current_upload_id" if _normalize(item.get("current_upload_id")) else "upload_id"
        update_result = _col("vault_items").update_one(
            {"_id": item.get("_id"), current_field: item.get(current_field)},
            {"$set": item_fields},
        )
        if getattr(update_result, "matched_count", 1) == 0:
            raise ValueError("Vault asset changed during replacement; reload and try again.")
    else:
        _update_by_id("vault_items", canonical_item_id, item_fields)
    _update_by_id(
        "uploaded_files",
        canonical_upload_id,
        {
            "vault_item_id": canonical_item_id,
            "version": next_version,
            "replaces_upload_id": normalized_replaces or None,
            "is_current_version": True,
            "replacement_status": "current",
            "updated_at": now,
        },
    )
    if normalized_replaces:
        _update_by_id(
            "uploaded_files",
            normalized_replaces,
            {
                "replaced_by_upload_id": canonical_upload_id,
                "is_current_version": False,
                "replacement_status": "superseded",
                "updated_at": now,
            },
        )
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "link_upload" if next_version == 1 else "replace_upload",
        details={
            "upload_id": canonical_upload_id,
            "version": next_version,
            "replaces_upload_id": normalized_replaces or None,
        },
    )
    return _serialize_item(_find_by_id("vault_items", canonical_item_id) or item)


def _vault_item_type_for_upload(upload: dict[str, Any]) -> str:
    asset_type = _normalize(upload.get("asset_type")).lower()
    content_type = _normalize(upload.get("content_type")).lower()
    category = _normalize(upload.get("category")).lower()
    if asset_type == "vault_photo" or content_type.startswith("image/") or category == "member_photo":
        return "photo"
    if (
        asset_type == "vault_document"
        or content_type == "application/pdf"
        or category == "verification_evidence"
    ):
        return "document"
    if content_type.startswith("audio/"):
        return "audio"
    if content_type.startswith("video/"):
        return "video"
    return "other"


def _vault_scope_for_upload(upload: dict[str, Any]) -> str:
    scope = _normalize(upload.get("vault_scope")).lower()
    if scope in {"personal", "household", "linked_family", "memorial", "organization"}:
        return scope
    if scope in {"family_shared", "household_private", "branch_shared"}:
        return "household"
    if scope in {"linked_family_shared", "all_linked"}:
        return "linked_family"
    if scope in {"public", "public_memorial"}:
        return "memorial"
    if scope in {"org", "organization_record", "organization_records"}:
        return "organization"
    if scope:
        raise ValueError("Unsupported upload vault_scope; refusing to downgrade it to personal.")
    return "personal"


def _vault_privacy_for_upload(upload: dict[str, Any]) -> str:
    scope = _normalize(
        upload.get("privacy_classification")
        or upload.get("privacy_scope")
        or upload.get("visibility_scope")
    ).lower()
    if scope == "private_to_owner_and_co_owner":
        return "owner_and_co_owner"
    if scope == "household_private":
        return "household_admins"
    if scope in {"linked_family_shared", "branch_shared"}:
        return "all_linked"
    if scope in {"public", "public_memorial"}:
        return "public_memorial"
    return "private_owner"


def ensure_vault_item_for_upload(
    uploaded_file: dict[str, Any] | str,
    owner_user_id: str,
    *,
    vault_item_id: str = "",
    authorized_project_id: str = "",
    replaces_upload_id: str = "",
    workspace_member_role: str = "",
) -> dict[str, Any]:
    supplied_record = uploaded_file if isinstance(uploaded_file, dict) else {}
    upload_id = _normalize(
        uploaded_file
        if isinstance(uploaded_file, str)
        else uploaded_file.get("_id") or uploaded_file.get("id")
    )
    if not upload_id:
        raise ValueError("Uploaded file id is required.")
    stored_upload = _find_by_id("uploaded_files", upload_id)
    if not stored_upload:
        raise ValueError("Vault upload not found.")
    upload = {**stored_upload, **supplied_record}
    project_id = _normalize(upload.get("project_id"))
    if _normalize(authorized_project_id) and project_id != _normalize(authorized_project_id):
        raise PermissionError("Vault upload does not belong to the active workspace.")
    if _normalize(upload.get("uploaded_by_user_id")) not in {"", _normalize(owner_user_id)}:
        raise PermissionError("Only the upload owner can create its vault item.")
    if bool(upload.get("quarantined")):
        raise ValueError("Quarantined uploads cannot be linked to a vault item.")
    scan_status = _normalize(upload.get("scan_status")).lower()
    if scan_status and scan_status not in {"pending", "clean"}:
        raise ValueError("Only pending or clean uploads can be linked to a vault item.")
    if upload.get("account_access_enabled") is False or bool(upload.get("owner_account_deleted")):
        raise ValueError("This upload is not available for vault access.")
    requested_version = int(upload.get("version") or 1)
    requested_replacement = _normalize(replaces_upload_id or upload.get("replaces_upload_id"))

    target_item_id = _normalize(vault_item_id or upload.get("vault_item_id"))
    if not target_item_id:
        current_items = _reverse_linked_current_items(upload_id)
        if len(current_items) > 1:
            raise PermissionError("Vault upload has ambiguous reverse linkage.")
        if current_items:
            target_item_id = _str_id(current_items[0].get("_id"))
    if not target_item_id and requested_replacement:
        replacement_items = _reverse_linked_current_items(requested_replacement)
        if not replacement_items:
            raise ValueError("The upload being replaced is not linked to a current vault item.")
        if len(replacement_items) != 1:
            raise PermissionError("The upload being replaced has ambiguous Vault linkage.")
        target_item_id = _str_id(replacement_items[0].get("_id"))
    if target_item_id:
        return link_vault_upload(
            target_item_id,
            upload_id,
            owner_user_id,
            authorized_project_id=_normalize(authorized_project_id) or project_id,
            family_id=_normalize(upload.get("family_id")),
            member_id=_normalize(upload.get("member_id")),
            version=requested_version,
            replaces_upload_id=requested_replacement,
            workspace_member_role=workspace_member_role,
        )

    title = Path(_normalize(upload.get("original_filename"))).name[:200]
    release_state = _normalize(upload.get("release_state")).lower() or "released"
    if release_state not in {"draft", "scheduled", "released"}:
        raise ValueError("Upload release_state must be draft, scheduled, or released.")
    reveal_at = _parse_iso_datetime(upload.get("reveal_at"))
    if release_state == "scheduled":
        if reveal_at is None or reveal_at <= _now_dt():
            raise ValueError("Scheduled uploads require a future reveal_at.")
    elif reveal_at is not None:
        raise ValueError("reveal_at is allowed only for scheduled uploads.")
    payload = VaultItemCreate(
        project_id=project_id,
        family_id=_normalize(upload.get("family_id")) or None,
        member_id=_normalize(upload.get("member_id")) or None,
        title=title or f"Vault upload {upload_id}",
        item_type=_vault_item_type_for_upload(upload),
        vault_scope=_vault_scope_for_upload(upload),
        privacy=_vault_privacy_for_upload(upload),
        release_state=cast(Any, release_state),
        reveal_at=reveal_at,
        metadata={
            "upload_category": _normalize(upload.get("category")) or None,
            "asset_type": _normalize(upload.get("asset_type")) or None,
        },
    )
    created = create_vault_item(
        payload,
        owner_user_id,
        authorized_project_id=_normalize(authorized_project_id) or project_id,
    )
    return link_vault_upload(
        _normalize(created.get("id")),
        upload_id,
        owner_user_id,
        authorized_project_id=_normalize(authorized_project_id) or project_id,
        family_id=_normalize(upload.get("family_id")),
        member_id=_normalize(upload.get("member_id")),
        version=requested_version,
        replaces_upload_id=requested_replacement,
        workspace_member_role=workspace_member_role,
    )


def _current_item_upload_id(item: dict[str, Any]) -> str:
    return _normalize(item.get("current_upload_id") or item.get("upload_id"))


def _asset_version_deleted(entry: dict[str, Any]) -> bool:
    return _normalize(entry.get("deletion_status")).lower() in {
        "pending",
        "failed",
        "deleted",
    }


def _reverse_linked_current_items(upload_id: str) -> list[dict[str, Any]]:
    """Resolve exact current reverse pointers without inferring old versions."""

    canonical_upload_id = _normalize(upload_id)
    matches: dict[str, dict[str, Any]] = {}
    candidate_values: list[Any] = [canonical_upload_id]
    if ObjectId.is_valid(canonical_upload_id):
        candidate_values.append(ObjectId(canonical_upload_id))
    for field in ("current_upload_id", "upload_id"):
        for candidate_value in candidate_values:
            for raw_item in _col("vault_items").find({field: candidate_value}):
                item = cast(dict[str, Any], raw_item)
                # ``upload_id`` may remain as stale migration data on a record that
                # already has a different canonical current_upload_id. Never use
                # that stale pointer to infer access to a superseded version.
                if _current_item_upload_id(item) != canonical_upload_id:
                    continue
                matches[_str_id(item.get("_id"))] = item
    return list(matches.values())


def _legacy_asset_version_entry(
    item: dict[str, Any],
    upload: dict[str, Any],
    *,
    actor_user_id: str,
) -> dict[str, Any]:
    try:
        version = max(int(item.get("asset_version") or upload.get("version") or 1), 1)
    except (TypeError, ValueError):
        version = 1
    return {
        "version": version,
        "upload_id": _str_id(upload.get("_id")),
        "replaces_upload_id": _normalize(upload.get("replaces_upload_id")) or None,
        "original_filename": _normalize(upload.get("original_filename")) or None,
        "content_type": _normalize(upload.get("content_type")) or None,
        "size_bytes": upload.get("size_bytes"),
        "scan_status": _normalize(upload.get("scan_status")).lower() or "pending",
        "created_at": upload.get("created_at") or item.get("created_at") or _now(),
        "created_by_user_id": _normalize(upload.get("uploaded_by_user_id")) or None,
        "migration_backfilled": True,
        "backfilled_at": _now(),
        "backfilled_by_user_id": _normalize(actor_user_id),
    }


def _backfill_legacy_upload_linkage(
    item: dict[str, Any],
    upload: dict[str, Any],
    *,
    actor_user_id: str,
) -> dict[str, Any]:
    canonical_item_id = _str_id(item.get("_id"))
    canonical_upload_id = _str_id(upload.get("_id"))
    if item.get("asset_versions"):
        raise PermissionError("Vault upload version metadata is inconsistent.")
    if _current_item_upload_id(item) != canonical_upload_id:
        raise PermissionError("Only an exact current legacy upload pointer can be backfilled.")
    linked_item_id = _normalize(upload.get("vault_item_id"))
    if linked_item_id and linked_item_id != canonical_item_id:
        raise PermissionError("Vault upload linkage does not match its item.")

    entry = _legacy_asset_version_entry(item, upload, actor_user_id=actor_user_id)
    pointer_field = (
        "current_upload_id"
        if _normalize(item.get("current_upload_id"))
        else "upload_id"
    )
    now = _now()
    update_result = _col("vault_items").update_one(
        {"_id": item.get("_id"), pointer_field: item.get(pointer_field)},
        {
            "$set": {
                "asset_versions": [entry],
                "asset_version": entry["version"],
                "updated_at": now,
            }
        },
    )
    if getattr(update_result, "matched_count", 1) == 0:
        raise ValueError("Vault asset changed during legacy linkage backfill; reload and try again.")
    _update_by_id(
        "uploaded_files",
        canonical_upload_id,
        {
            "vault_item_id": canonical_item_id,
            "version": entry["version"],
            "is_current_version": True,
            "replacement_status": "current",
            "vault_linkage_backfilled_at": now,
            "updated_at": now,
        },
    )
    log_vault_audit_event(
        canonical_item_id,
        actor_user_id,
        "backfill_upload_linkage",
        details={"upload_id": canonical_upload_id, "version": entry["version"]},
    )
    return _find_by_id("vault_items", canonical_item_id) or item


def authorize_vault_upload_access(
    upload_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
    requesting_workspace_role: str = "",
    relationship_scope: str = "",
    link_status: str = "",
    require_current: bool = False,
    backfill_legacy_linkage: bool = True,
) -> dict[str, Any]:
    upload = _find_by_id("uploaded_files", upload_id)
    if not upload:
        raise ValueError("Vault upload not found.")
    item_id = _normalize(upload.get("vault_item_id"))
    if item_id:
        item = _find_by_id("vault_items", item_id)
        if item is None:
            raise ValueError("Vault item not found.")
    else:
        reverse_matches = _reverse_linked_current_items(upload_id)
        if not reverse_matches:
            raise ValueError("Vault upload is not linked to a vault item.")
        if len(reverse_matches) != 1:
            raise PermissionError("Vault upload has ambiguous reverse linkage.")
        item = reverse_matches[0]
        item_id = _str_id(item.get("_id"))

    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id = _str_id(item.get("_id"))
    if item_id != canonical_item_id:
        raise PermissionError("Vault upload linkage does not match its item.")
    if _normalize(upload.get("project_id")) != _item_project_id(item):
        raise PermissionError("Vault upload does not belong to the item's workspace.")
    if (
        _normalize(item.get("family_id"))
        and _normalize(upload.get("family_id")) != _normalize(item.get("family_id"))
    ):
        raise PermissionError("Vault upload does not belong to the item's family.")
    if (
        _normalize(item.get("member_id"))
        and _normalize(upload.get("member_id")) != _normalize(item.get("member_id"))
    ):
        raise PermissionError("Vault upload does not belong to the item's family member.")

    is_owner = _normalize(item.get("owner_user_id")) == _normalize(requesting_user_id)
    if not is_owner:
        if not _privacy_allows(
            item,
            user_id=requesting_user_id,
            workspace_role=requesting_workspace_role,
            link_status=link_status,
        ):
            raise ValueError("Access denied.")
        if not _release_allows(
            item,
            user_id=requesting_user_id,
            workspace_role=requesting_workspace_role,
            relationship_scope=relationship_scope,
            link_status=link_status,
        ):
            raise ValueError("Vault item is not released to this user.")

    canonical_upload_id = _str_id(upload.get("_id"))
    versions = [
        dict(value)
        for value in item.get("asset_versions") or []
        if isinstance(value, dict)
    ]
    linked_entry = next(
        (
            value
            for value in versions
            if _normalize(value.get("upload_id")) == canonical_upload_id
        ),
        None,
    )
    legacy_current = not versions and _current_item_upload_id(item) == canonical_upload_id
    if linked_entry is None and not legacy_current:
        raise PermissionError("Vault upload version is not linked to this item.")
    if linked_entry is not None and _asset_version_deleted(linked_entry):
        raise PermissionError("Vault upload version has been deleted.")
    if (require_current or not is_owner) and _current_item_upload_id(item) != canonical_upload_id:
        raise PermissionError("Only the owner can access superseded vault versions.")
    if bool(upload.get("quarantined")) or _normalize(upload.get("scan_status")).lower() != "clean":
        raise ValueError("Vault upload has not passed its security scan.")
    if _normalize(upload.get("deletion_status")).lower() in {"pending", "failed", "deleted"}:
        raise ValueError("Vault upload is in a deletion state.")
    if _normalize(upload.get("vault_version_deletion_status")).lower() == "deleted":
        raise ValueError("Vault upload version has been deleted.")
    if _normalize(upload.get("replacement_status")).lower() == "deleted":
        raise ValueError("Vault upload version has been deleted.")
    if upload.get("account_access_enabled") is False or bool(upload.get("owner_account_deleted")):
        raise ValueError("Vault upload access is disabled.")

    if legacy_current and backfill_legacy_linkage:
        item = _backfill_legacy_upload_linkage(
            item,
            upload,
            actor_user_id=requesting_user_id,
        )
    elif (
        linked_entry is not None
        and not _normalize(upload.get("vault_item_id"))
        and _current_item_upload_id(item) == canonical_upload_id
        and backfill_legacy_linkage
    ):
        now = _now()
        _update_by_id(
            "uploaded_files",
            canonical_upload_id,
            {
                "vault_item_id": canonical_item_id,
                "version": linked_entry.get("version") or item.get("asset_version") or 1,
                "is_current_version": True,
                "replacement_status": "current",
                "vault_linkage_backfilled_at": now,
                "updated_at": now,
            },
        )
        log_vault_audit_event(
            canonical_item_id,
            requesting_user_id,
            "backfill_upload_denormalization",
            details={"upload_id": canonical_upload_id},
        )
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "access_upload",
        details={"upload_id": canonical_upload_id, "require_current": require_current},
    )
    serialized = _serialize_item(item)
    if not serialized:
        raise ValueError("Vault item not found.")
    return serialized


def _can_delete_vault_asset_version(
    item: dict[str, Any],
    requesting_user_id: str,
    *,
    workspace_member_role: str,
) -> bool:
    if _normalize(item.get("owner_user_id")) == _normalize(requesting_user_id):
        return True
    if _can_manage_item(item, requesting_user_id, roles=("steward",)):
        return True
    privacy = _normalize(item.get("privacy")).lower()
    role = _normalize(workspace_member_role).lower()
    if privacy == "owner_and_co_owner":
        return role in {"billing_owner", "co_owner"}
    if privacy in {"household_admins", "all_linked", "public_memorial"}:
        return role in HOUSEHOLD_ADMIN_ROLES
    return False


def _validate_upload_item_linkage_for_deletion(
    item: dict[str, Any],
    upload: dict[str, Any],
    *,
    upload_id: str,
    legacy_current: bool,
) -> None:
    canonical_item_id = _str_id(item.get("_id"))
    linked_item_id = _normalize(upload.get("vault_item_id"))
    if linked_item_id:
        if linked_item_id != canonical_item_id:
            raise PermissionError("Vault upload linkage does not match its item.")
    elif not legacy_current:
        raise PermissionError("Vault upload is missing canonical item linkage.")
    if _normalize(upload.get("project_id")) != _item_project_id(item):
        raise PermissionError("Vault upload does not belong to the item's workspace.")
    if (
        _normalize(item.get("family_id"))
        and _normalize(upload.get("family_id")) != _normalize(item.get("family_id"))
    ):
        raise PermissionError("Vault upload does not belong to the item's family.")
    if (
        _normalize(item.get("member_id"))
        and _normalize(upload.get("member_id")) != _normalize(item.get("member_id"))
    ):
        raise PermissionError("Vault upload does not belong to the item's family member.")
    if _str_id(upload.get("_id")) != _normalize(upload_id):
        raise PermissionError("Vault upload id does not match the requested version.")


def _usable_prior_asset_version(
    item: dict[str, Any],
    versions: Iterable[dict[str, Any]],
    *,
    deleted_upload_id: str,
    deleted_version: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for raw_entry in versions:
        entry = dict(raw_entry)
        candidate_upload_id = _normalize(entry.get("upload_id"))
        if not candidate_upload_id or candidate_upload_id == deleted_upload_id:
            continue
        if _asset_version_deleted(entry):
            continue
        try:
            candidate_version = int(entry.get("version") or 0)
        except (TypeError, ValueError):
            continue
        if candidate_version < 1 or candidate_version >= deleted_version:
            continue
        upload = _find_by_id("uploaded_files", candidate_upload_id)
        if not upload:
            continue
        if _normalize(upload.get("vault_item_id")) != _str_id(item.get("_id")):
            continue
        if _normalize(upload.get("project_id")) != _item_project_id(item):
            continue
        if (
            _normalize(item.get("family_id"))
            and _normalize(upload.get("family_id")) != _normalize(item.get("family_id"))
        ):
            continue
        if (
            _normalize(item.get("member_id"))
            and _normalize(upload.get("member_id")) != _normalize(item.get("member_id"))
        ):
            continue
        if bool(upload.get("quarantined")):
            continue
        if _normalize(upload.get("scan_status")).lower() != "clean":
            continue
        if _normalize(upload.get("deletion_status")).lower() in {"pending", "failed", "deleted"}:
            continue
        if _normalize(upload.get("vault_version_deletion_status")).lower() == "deleted":
            continue
        if _normalize(upload.get("replacement_status")).lower() == "deleted":
            continue
        if upload.get("account_access_enabled") is False or bool(upload.get("owner_account_deleted")):
            continue
        candidates.append((candidate_version, entry, upload))
    if not candidates:
        return None
    _, entry, upload = max(candidates, key=lambda value: value[0])
    return entry, upload


def _public_upload_deletion_result(plan: dict[str, Any], *, committed: bool) -> dict[str, Any]:
    return {
        "vault_item_id": plan["vault_item_id"],
        "upload_id": plan["upload_id"],
        "allowed": True,
        "already_tombstoned": bool(plan["already_tombstoned"]),
        "was_current": bool(plan["was_current"]),
        "promoted_upload_id": plan.get("promoted_upload_id"),
        "promoted_version": plan.get("promoted_version"),
        "item_closed": bool(plan["item_closed"]),
        "remaining_versions": int(plan.get("remaining_versions") or 0),
        # Physical uploaded_files/R2 cleanup is safe only after the mutating
        # tombstone operation has moved or cleared the canonical item pointer.
        "safe_to_delete_upload": committed,
    }


def _vault_upload_version_deletion_plan(
    vault_item_id: str,
    upload_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
    workspace_member_role: str,
) -> dict[str, Any]:
    item = _find_by_id("vault_items", vault_item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    if not _can_delete_vault_asset_version(
        item,
        requesting_user_id,
        workspace_member_role=workspace_member_role,
    ):
        raise PermissionError("Only the owner or an authorized Vault manager can delete this version.")

    canonical_item_id = _str_id(item.get("_id"))
    canonical_upload_id = _normalize(upload_id)
    versions = [
        dict(value)
        for value in item.get("asset_versions") or []
        if isinstance(value, dict)
    ]
    current_upload_id = _current_item_upload_id(item)
    matching_indexes = [
        index
        for index, entry in enumerate(versions)
        if _normalize(entry.get("upload_id")) == canonical_upload_id
    ]
    if len(matching_indexes) > 1:
        raise PermissionError("Vault upload has duplicate version linkage.")
    legacy_current = not versions and current_upload_id == canonical_upload_id
    upload = _find_by_id("uploaded_files", canonical_upload_id)
    if not matching_indexes:
        if not legacy_current:
            raise PermissionError("Vault upload version is not linked to this item.")
        if not upload:
            raise ValueError("Vault upload not found.")
        versions = [
            _legacy_asset_version_entry(
                item,
                upload,
                actor_user_id=requesting_user_id,
            )
        ]
        matching_indexes = [0]

    entry_index = matching_indexes[0]
    entry = versions[entry_index]
    already_tombstoned = _normalize(entry.get("deletion_status")).lower() == "deleted"
    if already_tombstoned:
        return {
            "vault_item_id": canonical_item_id,
            "upload_id": canonical_upload_id,
            "item": item,
            "upload": upload,
            "versions": versions,
            "entry_index": entry_index,
            "already_tombstoned": True,
            "was_current": bool(entry.get("was_current_at_deletion")),
            "promoted_upload_id": _normalize(entry.get("promoted_upload_id_on_delete")) or None,
            "promoted_version": entry.get("promoted_version_on_delete"),
            "item_closed": bool(entry.get("item_closed_on_delete")),
            "remaining_versions": sum(
                1 for value in versions if not _asset_version_deleted(value)
            ),
            "promoted_upload": None,
        }

    _assert_item_operable(item)
    if not upload:
        raise ValueError("Vault upload not found.")
    _validate_upload_item_linkage_for_deletion(
        item,
        upload,
        upload_id=canonical_upload_id,
        legacy_current=legacy_current,
    )
    was_current = current_upload_id == canonical_upload_id
    try:
        deleted_version = max(int(entry.get("version") or upload.get("version") or 1), 1)
    except (TypeError, ValueError):
        deleted_version = 1
    promoted = (
        _usable_prior_asset_version(
            item,
            versions,
            deleted_upload_id=canonical_upload_id,
            deleted_version=deleted_version,
        )
        if was_current
        else None
    )
    promoted_entry, promoted_upload = promoted if promoted else (None, None)
    promoted_upload_id = (
        _normalize(promoted_entry.get("upload_id")) if promoted_entry else None
    )
    promoted_version = int(promoted_entry.get("version")) if promoted_entry else None
    remaining_versions = sum(
        1
        for value in versions
        if _normalize(value.get("upload_id")) != canonical_upload_id
        and not _asset_version_deleted(value)
    )
    return {
        "vault_item_id": canonical_item_id,
        "upload_id": canonical_upload_id,
        "item": item,
        "upload": upload,
        "versions": versions,
        "entry_index": entry_index,
        "already_tombstoned": False,
        "was_current": was_current,
        "promoted_upload_id": promoted_upload_id,
        "promoted_version": promoted_version,
        "item_closed": bool(was_current and promoted_entry is None),
        "remaining_versions": remaining_versions,
        "promoted_upload": promoted_upload,
    }


def preview_vault_upload_version_deletion(
    vault_item_id: str,
    upload_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
    workspace_member_role: str = "",
) -> dict[str, Any]:
    """Authorize and describe a Vault upload deletion without mutating state."""

    plan = _vault_upload_version_deletion_plan(
        vault_item_id,
        upload_id,
        requesting_user_id,
        authorized_project_id=authorized_project_id,
        workspace_member_role=workspace_member_role,
    )
    return _public_upload_deletion_result(plan, committed=bool(plan["already_tombstoned"]))


def tombstone_vault_upload_version(
    vault_item_id: str,
    upload_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
    workspace_member_role: str = "",
    reason: str = "customer_delete",
) -> dict[str, Any]:
    """Detach a Vault version before uploaded_files/R2 physical cleanup.

    The retained version tombstone makes this operation retry-safe even after
    the uploaded_files document has been removed by the caller. The item is
    updated first, so no successful return can leave current_upload_id pointing
    at the version the caller is about to physically delete.
    """

    plan = _vault_upload_version_deletion_plan(
        vault_item_id,
        upload_id,
        requesting_user_id,
        authorized_project_id=authorized_project_id,
        workspace_member_role=workspace_member_role,
    )
    if plan["already_tombstoned"]:
        retry_at = _now()
        retained_entry = plan["versions"][plan["entry_index"]]
        retained_reason = _normalize(retained_entry.get("deletion_reason")) or "customer_delete"
        if plan.get("upload"):
            _update_by_id(
                "uploaded_files",
                plan["upload_id"],
                {
                    "vault_item_id": plan["vault_item_id"],
                    "version": retained_entry.get("version") or 1,
                    "is_current_version": False,
                    "replacement_status": "deleted",
                    "vault_version_deletion_status": "deleted",
                    "vault_version_deleted_at": retained_entry.get("deleted_at") or retry_at,
                    "vault_version_deleted_by_user_id": (
                        retained_entry.get("deleted_by_user_id") or requesting_user_id
                    ),
                    "vault_version_deletion_reason": retained_reason,
                    "updated_at": retry_at,
                },
            )
        if plan.get("promoted_upload_id"):
            _update_by_id(
                "uploaded_files",
                plan["promoted_upload_id"],
                {
                    "is_current_version": True,
                    "replacement_status": "current",
                    "replaced_by_upload_id": None,
                    "updated_at": retry_at,
                },
            )
        log_vault_audit_event(
            plan["vault_item_id"],
            requesting_user_id,
            "delete_upload_version_retry",
            details={"upload_id": plan["upload_id"]},
        )
        return _public_upload_deletion_result(plan, committed=True)

    now = _now()
    normalized_reason = _normalize(reason)[:200] or "customer_delete"
    versions = plan["versions"]
    entry = versions[plan["entry_index"]]
    entry.update(
        {
            "deletion_status": "deleted",
            "deleted_at": now,
            "deleted_by_user_id": _normalize(requesting_user_id),
            "deletion_reason": normalized_reason,
            "was_current_at_deletion": plan["was_current"],
            "promoted_upload_id_on_delete": plan.get("promoted_upload_id"),
            "promoted_version_on_delete": plan.get("promoted_version"),
            "item_closed_on_delete": plan["item_closed"],
        }
    )
    item = plan["item"]
    item_fields: dict[str, Any] = {"asset_versions": versions, "updated_at": now}
    if plan["was_current"]:
        if plan.get("promoted_upload_id"):
            item_fields.update(
                {
                    "upload_id": plan["promoted_upload_id"],
                    "current_upload_id": plan["promoted_upload_id"],
                    "asset_version": plan["promoted_version"],
                }
            )
        else:
            item_fields.update(
                {
                    "upload_id": None,
                    "current_upload_id": None,
                    "asset_version": None,
                    "status": "closed",
                    "access_enabled": False,
                    "closed_at": now,
                    "closed_by_user_id": _normalize(requesting_user_id),
                    "closure_reason": "no_available_asset_version",
                }
            )

    expected_current = _current_item_upload_id(item)
    item_query: dict[str, Any] = {"_id": item.get("_id")}
    if expected_current:
        current_field = (
            "current_upload_id"
            if _normalize(item.get("current_upload_id"))
            else "upload_id"
        )
        item_query[current_field] = item.get(current_field)
    if item.get("updated_at") is not None:
        item_query["updated_at"] = item.get("updated_at")
    update_result = _col("vault_items").update_one(item_query, {"$set": item_fields})
    if getattr(update_result, "matched_count", 1) == 0:
        raise ValueError("Vault asset changed during deletion; reload and try again.")

    target_upload = plan.get("upload")
    if target_upload:
        _update_by_id(
            "uploaded_files",
            plan["upload_id"],
            {
                "vault_item_id": plan["vault_item_id"],
                "version": entry.get("version") or 1,
                "is_current_version": False,
                "replacement_status": "deleted",
                "vault_version_deletion_status": "deleted",
                "vault_version_deleted_at": now,
                "vault_version_deleted_by_user_id": _normalize(requesting_user_id),
                "vault_version_deletion_reason": normalized_reason,
                "updated_at": now,
            },
        )
    if plan.get("promoted_upload_id"):
        _update_by_id(
            "uploaded_files",
            plan["promoted_upload_id"],
            {
                "is_current_version": True,
                "replacement_status": "current",
                "replaced_by_upload_id": None,
                "updated_at": now,
            },
        )
    log_vault_audit_event(
        plan["vault_item_id"],
        requesting_user_id,
        "delete_upload_version",
        details={
            "upload_id": plan["upload_id"],
            "version": entry.get("version"),
            "was_current": plan["was_current"],
            "promoted_upload_id": plan.get("promoted_upload_id"),
            "promoted_version": plan.get("promoted_version"),
            "item_closed": plan["item_closed"],
            "reason": normalized_reason,
        },
    )
    return _public_upload_deletion_result(plan, committed=True)


# Vault collections

def create_vault_collection(
    payload: VaultCollectionCreate,
    owner_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    project_id = _normalize(payload.project_id)
    if _normalize(authorized_project_id) and project_id != _normalize(authorized_project_id):
        raise PermissionError("Vault collection project must match the active workspace.")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "project_id": project_id,
        "owner_user_id": _normalize(owner_user_id),
        "status": "active",
        "access_enabled": True,
        "created_at": now,
        "updated_at": now,
    }
    result = _col("vault_collections").insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_vault_collections(
    project_id: str,
    owner_user_id: str,
    *,
    authorized_project_id: str = "",
    requesting_workspace_role: str = "",
    link_status: str = "",
    allowed_vault_scopes: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    project_id = _normalize(project_id)
    if _normalize(authorized_project_id) and project_id != _normalize(authorized_project_id):
        raise PermissionError("Requested project does not match the active workspace.")
    role = _normalize(requesting_workspace_role).lower()
    active_link = _normalize(link_status).lower() in ACTIVE_LINK_STATUSES
    allowed_scopes = (
        {
            _normalize(scope).lower()
            for scope in allowed_vault_scopes
            if _normalize(scope)
        }
        if allowed_vault_scopes is not None
        else None
    )
    visible: list[dict[str, Any]] = []
    for raw_doc in _col("vault_collections").find({"project_id": project_id}):
        doc = cast(dict[str, Any], raw_doc)
        if allowed_scopes is not None and _normalize(doc.get("vault_scope")).lower() not in allowed_scopes:
            continue
        if doc.get("access_enabled") is False or _normalize(doc.get("status")).lower() in {
            "closed",
            "deleted",
        }:
            continue
        if _normalize(doc.get("owner_user_id")) == _normalize(owner_user_id):
            visible.append(doc)
            continue
        privacy = _normalize(doc.get("privacy")).lower()
        if privacy == "owner_and_co_owner" and _has_owner_and_co_owner_access(role, link_status):
            visible.append(doc)
        elif privacy == "household_admins" and _has_household_admin_access(role, link_status):
            visible.append(doc)
        elif privacy in {"all_linked", "public_memorial"} and role in WORKSPACE_READ_ROLES and active_link:
            visible.append(doc)
    return [_serialize(doc) or {} for doc in visible]


# Vault access grants

def _find_grant_for_item(item_id: str, grant_id: str) -> dict[str, Any]:
    grant = _find_by_id("vault_access_grants", grant_id)
    if not grant or _normalize(grant.get("vault_item_id")) != item_id:
        raise ValueError("Vault access grant not found for this item.")
    return grant


def _assert_can_manage_grants(item: dict[str, Any], user_id: str) -> tuple[str, bool]:
    item_id = _str_id(item.get("_id"))
    is_owner = _normalize(item.get("owner_user_id")) == _normalize(user_id)
    if not is_owner and not _can_manage_item(item, user_id, roles=("steward",)):
        raise PermissionError("Only the owner or steward can manage grants.")
    return item_id, is_owner


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
    _assert_item_operable(item)
    canonical_item_id, is_owner = _assert_can_manage_grants(item, granting_user_id)
    role = _normalize(payload.permission_role).lower()
    if role == "owner":
        raise ValueError("Ownership cannot be assigned through a vault access grant.")
    if not is_owner and role in {"steward", "executor"}:
        raise PermissionError("Only the owner can grant steward or executor access.")
    grantee_user_id = _normalize(payload.grantee_user_id)
    grantee_project_id = _normalize(payload.grantee_project_id)
    if grantee_project_id and grantee_project_id != _item_project_id(item):
        raise PermissionError("Cross-project vault grants are not allowed.")
    if grantee_user_id:
        _validate_user_reference(grantee_user_id, label="Vault grantee")
    if payload.expires_at is not None:
        expires_at = payload.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at.astimezone(timezone.utc) <= _now_dt():
            raise ValueError("Vault grant expires_at must be in the future.")
    for raw_grant in _col("vault_access_grants").find({"vault_item_id": canonical_item_id}):
        grant = cast(dict[str, Any], raw_grant)
        if (
            _is_grant_active(grant)
            and _normalize(grant.get("grantee_user_id")) == grantee_user_id
            and _normalize(grant.get("grantee_project_id")) == grantee_project_id
        ):
            raise ValueError("An active grant already exists for this grantee.")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(exclude={"expires_at"}),
        "vault_item_id": canonical_item_id,
        "grantee_user_id": grantee_user_id or None,
        "grantee_project_id": grantee_project_id or None,
        "permission_role": role,
        "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        "status": "active",
        "access_enabled": True,
        "granted_by_user_id": _normalize(granting_user_id),
        "created_at": now,
        "updated_at": now,
    }
    result = _col("vault_access_grants").insert_one(doc)
    doc["_id"] = result.inserted_id
    log_vault_audit_event(
        canonical_item_id,
        granting_user_id,
        "grant_access",
        details={
            "grant_id": _str_id(result.inserted_id),
            "grantee_user_id": grantee_user_id or None,
            "grantee_project_id": grantee_project_id or None,
            "permission_role": role,
            "expires_at": doc["expires_at"],
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
    _assert_item_operable(item)
    canonical_item_id, _ = _assert_can_manage_grants(item, requesting_user_id)
    return [
        _serialize(cast(dict[str, Any], doc)) or {}
        for doc in _col("vault_access_grants").find({"vault_item_id": canonical_item_id})
        if _normalize(cast(dict[str, Any], doc).get("status")).lower() != "deleted"
    ]


def update_vault_access_grant(
    item_id: str,
    grant_id: str,
    updates: VaultAccessGrantUpdate,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id, is_owner = _assert_can_manage_grants(item, requesting_user_id)
    grant = _find_grant_for_item(canonical_item_id, grant_id)
    if _normalize(grant.get("status")).lower() in INACTIVE_GRANT_STATUSES:
        raise ValueError("Revoked or deleted grants cannot be updated.")
    role = updates.permission_role or _normalize(grant.get("permission_role")) or "viewer"
    if role == "owner":
        raise ValueError("Ownership cannot be assigned through a vault access grant.")
    if not is_owner and role in {"steward", "executor"}:
        raise PermissionError("Only the owner can grant steward or executor access.")
    fields: dict[str, Any] = {"updated_at": _now()}
    if "permission_role" in updates.model_fields_set:
        fields["permission_role"] = role
    if "expires_at" in updates.model_fields_set:
        if updates.expires_at is not None:
            expires_at = updates.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at.astimezone(timezone.utc) <= _now_dt():
                raise ValueError("Vault grant expires_at must be in the future.")
            fields["expires_at"] = expires_at.isoformat()
        else:
            fields["expires_at"] = None
    canonical_grant_id = _str_id(grant.get("_id"))
    _update_by_id("vault_access_grants", canonical_grant_id, fields)
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "update_grant",
        details={"grant_id": canonical_grant_id, "fields": sorted(fields)},
    )
    return _serialize(_find_by_id("vault_access_grants", canonical_grant_id)) or {}


def revoke_vault_access_grant(
    item_id: str,
    grant_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id, is_owner = _assert_can_manage_grants(item, requesting_user_id)
    grant = _find_grant_for_item(canonical_item_id, grant_id)
    if not is_owner and _normalize(grant.get("permission_role")).lower() in {"steward", "executor"}:
        raise PermissionError("Only the owner can revoke steward or executor access.")
    if _normalize(grant.get("status")).lower() == "deleted":
        raise ValueError("Deleted grant cannot be revoked.")
    now = _now()
    canonical_grant_id = _str_id(grant.get("_id"))
    _update_by_id(
        "vault_access_grants",
        canonical_grant_id,
        {
            "status": "revoked",
            "access_enabled": False,
            "revoked_at": now,
            "revoked_by_user_id": requesting_user_id,
            "updated_at": now,
        },
    )
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "revoke_grant",
        details={"grant_id": canonical_grant_id},
    )
    return _serialize(_find_by_id("vault_access_grants", canonical_grant_id)) or {}


def delete_vault_access_grant(
    item_id: str,
    grant_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> bool:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id, is_owner = _assert_can_manage_grants(item, requesting_user_id)
    if not is_owner:
        raise PermissionError("Only the owner can delete a vault grant.")
    grant = _find_grant_for_item(canonical_item_id, grant_id)
    now = _now()
    canonical_grant_id = _str_id(grant.get("_id"))
    _update_by_id(
        "vault_access_grants",
        canonical_grant_id,
        {
            "status": "deleted",
            "access_enabled": False,
            "deleted_at": now,
            "deleted_by_user_id": requesting_user_id,
            "updated_at": now,
        },
    )
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "delete_grant",
        details={"grant_id": canonical_grant_id},
    )
    return True


# Vault release rules

def _find_rule_for_item(item_id: str, rule_id: str) -> dict[str, Any]:
    rule = _find_by_id("vault_release_rules", rule_id)
    if not rule or _normalize(rule.get("vault_item_id")) != item_id:
        raise ValueError("Vault release rule not found for this item.")
    return rule


def _assert_rule_owner(item: dict[str, Any], user_id: str) -> str:
    item_id = _str_id(item.get("_id"))
    if _normalize(item.get("owner_user_id")) != _normalize(user_id):
        raise PermissionError("Only the owner can manage release rules.")
    return item_id


def _normalized_release_payload(payload: VaultReleaseRuleCreate) -> dict[str, Any]:
    data = payload.model_dump()
    trigger = _normalize(payload.trigger_type).lower()
    if trigger == "to_named":
        data["release_to"] = "named_list"
    elif trigger == "to_spouse":
        data["release_to"] = "spouse"
    elif trigger == "to_descendants":
        data["release_to"] = "descendants"
    data["named_recipients"] = [
        _normalize(value) for value in payload.named_recipients if _normalize(value)
    ]
    return data


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
    _assert_item_operable(item)
    canonical_item_id = _assert_rule_owner(item, owner_user_id)
    if payload.trustee_user_id:
        _validate_user_reference(payload.trustee_user_id, label="Vault trustee")
        if _normalize(payload.trustee_user_id) == _normalize(owner_user_id):
            raise PermissionError("The item owner cannot self-certify a governed release event.")
    for recipient_id in payload.named_recipients:
        _validate_user_reference(recipient_id, label="Named Vault recipient")
    now = _now()
    doc: dict[str, Any] = {
        **_normalized_release_payload(payload),
        "vault_item_id": canonical_item_id,
        "status": "active",
        "access_enabled": True,
        "created_by_user_id": _normalize(owner_user_id),
        "created_at": now,
        "updated_at": now,
    }
    result = _col("vault_release_rules").insert_one(doc)
    doc["_id"] = result.inserted_id
    item_updates: dict[str, Any] = {"release_state": "scheduled", "updated_at": now}
    if payload.trigger_type == "on_date" and not _normalize(item.get("reveal_at")):
        trigger_at = _parse_iso_datetime(payload.trigger_value)
        item_updates["reveal_at"] = trigger_at.isoformat() if trigger_at else None
    _update_by_id("vault_items", canonical_item_id, item_updates)
    log_vault_audit_event(
        canonical_item_id,
        owner_user_id,
        "create_release_rule",
        details={
            "rule_id": _str_id(result.inserted_id),
            "trigger_type": _normalize(payload.trigger_type),
            "release_to": _normalize(doc.get("release_to")),
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
    _assert_item_operable(item)
    canonical_item_id = _assert_rule_owner(item, requesting_user_id)
    return [
        _serialize(cast(dict[str, Any], doc)) or {}
        for doc in _col("vault_release_rules").find({"vault_item_id": canonical_item_id})
        if _normalize(cast(dict[str, Any], doc).get("status")).lower() != "deleted"
    ]


def update_vault_release_rule(
    item_id: str,
    rule_id: str,
    updates: VaultReleaseRuleUpdate,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id = _str_id(item.get("_id"))
    rule = _find_rule_for_item(canonical_item_id, rule_id)
    if _normalize(rule.get("status")).lower() in {"revoked", "deleted", "disabled"}:
        raise ValueError("Revoked or deleted release rules cannot be updated.")
    is_owner = _normalize(item.get("owner_user_id")) == _normalize(requesting_user_id)
    is_trustee = _normalize(rule.get("trustee_user_id")) == _normalize(requesting_user_id)
    effective_trigger_type = _normalize(
        updates.trigger_type
        if "trigger_type" in updates.model_fields_set
        else rule.get("trigger_type")
    ).lower()
    trustee_satisfaction = (
        effective_trigger_type != "on_date"
        and updates.model_fields_set == {"status"}
        and updates.status == "satisfied"
        and not is_owner
    )
    if effective_trigger_type != "on_date" and updates.status == "satisfied" and not (
        is_trustee and trustee_satisfaction
    ):
        raise PermissionError("Only the named trustee can certify a governed release event.")
    if not is_owner and not (is_trustee and trustee_satisfaction):
        raise PermissionError("Only the owner, or the named trustee satisfying a rule, can update it.")
    merged = {
        "vault_item_id": canonical_item_id,
        "trigger_type": updates.trigger_type if "trigger_type" in updates.model_fields_set else rule.get("trigger_type"),
        "trigger_value": updates.trigger_value if "trigger_value" in updates.model_fields_set else rule.get("trigger_value"),
        "release_to": updates.release_to if "release_to" in updates.model_fields_set else rule.get("release_to"),
        "named_recipients": (
            updates.named_recipients
            if "named_recipients" in updates.model_fields_set
            else rule.get("named_recipients") or []
        ),
        "trustee_user_id": (
            updates.trustee_user_id
            if "trustee_user_id" in updates.model_fields_set
            else rule.get("trustee_user_id")
        ),
        "notes": updates.notes if "notes" in updates.model_fields_set else rule.get("notes"),
    }
    validated = VaultReleaseRuleCreate(**merged)
    if validated.trustee_user_id and (is_owner or "trustee_user_id" in updates.model_fields_set):
        _validate_user_reference(validated.trustee_user_id, label="Vault trustee")
        if _normalize(validated.trustee_user_id) == _normalize(item.get("owner_user_id")):
            raise PermissionError("The item owner cannot self-certify a governed release event.")
    if is_owner or "named_recipients" in updates.model_fields_set:
        for recipient_id in validated.named_recipients:
            _validate_user_reference(recipient_id, label="Named Vault recipient")
    normalized = _normalized_release_payload(validated)
    fields = {
        key: normalized[key]
        for key in updates.model_fields_set
        if key != "status" and key in normalized and key != "vault_item_id"
    }
    if "status" in updates.model_fields_set:
        fields["status"] = updates.status
        fields["satisfied_at"] = _now() if updates.status == "satisfied" else None
        fields["satisfied_by_user_id"] = requesting_user_id if updates.status == "satisfied" else None
    fields["updated_at"] = _now()
    canonical_rule_id = _str_id(rule.get("_id"))
    _update_by_id("vault_release_rules", canonical_rule_id, fields)
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "update_release_rule",
        details={"rule_id": canonical_rule_id, "fields": sorted(fields)},
    )
    return _serialize(_find_by_id("vault_release_rules", canonical_rule_id)) or {}


def revoke_vault_release_rule(
    item_id: str,
    rule_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> dict[str, Any]:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id = _assert_rule_owner(item, requesting_user_id)
    rule = _find_rule_for_item(canonical_item_id, rule_id)
    if _normalize(rule.get("status")).lower() == "deleted":
        raise ValueError("Deleted release rule cannot be revoked.")
    now = _now()
    canonical_rule_id = _str_id(rule.get("_id"))
    _update_by_id(
        "vault_release_rules",
        canonical_rule_id,
        {
            "status": "revoked",
            "access_enabled": False,
            "revoked_at": now,
            "revoked_by_user_id": requesting_user_id,
            "updated_at": now,
        },
    )
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "revoke_release_rule",
        details={"rule_id": canonical_rule_id},
    )
    return _serialize(_find_by_id("vault_release_rules", canonical_rule_id)) or {}


def delete_vault_release_rule(
    item_id: str,
    rule_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str = "",
) -> bool:
    item = _find_by_id("vault_items", item_id)
    if not item:
        raise ValueError("Vault item not found.")
    _assert_authorized_project(item, authorized_project_id=authorized_project_id)
    _assert_item_operable(item)
    canonical_item_id = _assert_rule_owner(item, requesting_user_id)
    rule = _find_rule_for_item(canonical_item_id, rule_id)
    now = _now()
    canonical_rule_id = _str_id(rule.get("_id"))
    _update_by_id(
        "vault_release_rules",
        canonical_rule_id,
        {
            "status": "deleted",
            "access_enabled": False,
            "deleted_at": now,
            "deleted_by_user_id": requesting_user_id,
            "updated_at": now,
        },
    )
    log_vault_audit_event(
        canonical_item_id,
        requesting_user_id,
        "delete_release_rule",
        details={"rule_id": canonical_rule_id},
    )
    return True


# Vault audit events

def log_vault_audit_event(
    item_id: str,
    user_id: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    _col("vault_audit_events").insert_one({
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
    _assert_item_operable(item)
    canonical_item_id = _str_id(item.get("_id"))
    is_owner = _normalize(item.get("owner_user_id")) == _normalize(requesting_user_id)
    if not is_owner:
        if _normalize(item.get("privacy")).lower() == "private_owner" or not _has_grant(
            canonical_item_id,
            requesting_user_id,
            roles=("executor",),
            project_id=_item_project_id(item),
        ):
            raise PermissionError("Only the owner or an active executor can view audit events.")
    docs = [
        cast(dict[str, Any], doc)
        for doc in _col("vault_audit_events").find({"vault_item_id": canonical_item_id})
    ]
    docs.sort(key=lambda value: _normalize(value.get("created_at")), reverse=True)
    return [_serialize(doc) or {} for doc in docs]
