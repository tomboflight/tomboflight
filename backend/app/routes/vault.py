from __future__ import annotations

from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_database
from app.dependencies.auth import get_current_user
from app.schemas.vault import (
    VaultAccessGrantCreate,
    VaultAccessGrantUpdate,
    VaultCollectionCreate,
    VaultItemCreate,
    VaultItemUpdate,
    VaultReleaseRuleCreate,
    VaultReleaseRuleUpdate,
)
from app.services.vault_service import (
    create_vault_access_grant,
    create_vault_collection,
    create_vault_item,
    create_vault_release_rule,
    delete_vault_access_grant,
    delete_vault_item,
    delete_vault_release_rule,
    get_vault_item,
    list_vault_access_grants,
    list_vault_audit_events,
    list_vault_collections,
    list_vault_items,
    list_vault_release_rules,
    revoke_vault_access_grant,
    revoke_vault_release_rule,
    update_vault_access_grant,
    update_vault_item,
    update_vault_release_rule,
)
from app.services.workspace_access_service import (
    require_workspace_capability,
    require_workspace_maintenance_write_access,
    require_workspace_member_role,
)

router = APIRouter(prefix="/vault", tags=["Vault"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


BASE_VAULT_CAPABILITIES = (
    "can_use_personal_vault",
    "can_use_household_vault",
    "can_use_linked_household_vault",
    "can_use_organization_records_vault",
)
# Backward-compatible export used by upload-hub integration checks.
HOUSEHOLD_VAULT_CAPABILITIES = ("can_use_household_vault",)
VAULT_SCOPE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    # Household vault access is a superset for operational personal records on
    # household plans whose catalog intentionally sets personal_vault false.
    "personal": ("can_use_personal_vault", "can_use_household_vault"),
    "household": ("can_use_household_vault",),
    "linked_family": ("can_use_linked_household_vault",),
    "memorial": ("can_use_personal_vault", "can_use_household_vault"),
    "organization": ("can_use_organization_records_vault",),
}
READ_VAULT_ROLES = (
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
    "viewer",
    "minor_viewer",
    "linked_relative",
    "legacy_executor",
)
CREATE_VAULT_ROLES = ("billing_owner", "co_owner", "family_manager", "contributor")


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _find_vault_item_by_id(item_id: str) -> dict[str, Any] | None:
    db = get_database()
    if ObjectId.is_valid(item_id):
        doc = db["vault_items"].find_one({"_id": ObjectId(item_id)})
        if doc:
            return doc
    return db["vault_items"].find_one({"_id": item_id})


def _find_vault_release_rule_by_id(rule_id: str) -> dict[str, Any] | None:
    db = get_database()
    if ObjectId.is_valid(rule_id):
        doc = db["vault_release_rules"].find_one({"_id": ObjectId(rule_id)})
        if doc:
            return doc
    return db["vault_release_rules"].find_one({"_id": rule_id})


def _resolve_vault_context(
    current_user: dict[str, Any],
    *,
    project_id: str,
    vault_scope: str = "",
) -> dict[str, Any]:
    normalized_scope = _normalize(vault_scope).lower()
    capabilities = (
        HOUSEHOLD_VAULT_CAPABILITIES
        if normalized_scope == "household"
        else VAULT_SCOPE_CAPABILITIES.get(normalized_scope, BASE_VAULT_CAPABILITIES)
    )
    return require_workspace_capability(
        current_user,
        project_id=project_id,
        capabilities=capabilities,
        detail="Your active package does not include this vault operation.",
    )


def _require_vault_role(
    context: dict[str, Any],
    *,
    write: bool = False,
    sensitive: bool = False,
    mutation: bool = False,
) -> None:
    # Item-level owner/grant checks in vault_service are authoritative for
    # existing items. Broad workspace admission here lets editor/steward/
    # executor grants work even when the base workspace role is read-only.
    if write:
        allowed_roles = CREATE_VAULT_ROLES
        detail = "Your workspace role cannot create vault records."
    else:
        allowed_roles = READ_VAULT_ROLES
        detail = (
            "Your role cannot manage this vault item."
            if sensitive
            else "Your role cannot access vault items."
        )
    require_workspace_member_role(context, allowed_roles=allowed_roles, detail=detail)
    if write or mutation:
        require_workspace_maintenance_write_access(context, feature_name="Vault")


def _require_additional_capability(
    current_user: dict[str, Any],
    *,
    project_id: str,
    capability: str,
    detail: str,
) -> None:
    require_workspace_capability(
        current_user,
        project_id=project_id,
        capabilities=(capability,),
        detail=detail,
    )


def _require_release_entitlements(
    current_user: dict[str, Any],
    *,
    project_id: str,
    release_state: str = "",
    reveal_at: Any = None,
    trigger_type: str = "",
) -> None:
    if _normalize(release_state).lower() == "scheduled" or reveal_at is not None or trigger_type:
        _require_additional_capability(
            current_user,
            project_id=project_id,
            capability="can_use_scheduled_reveal",
            detail="Your active package does not include scheduled vault release.",
        )
    if trigger_type and _normalize(trigger_type).lower() != "on_date":
        _require_additional_capability(
            current_user,
            project_id=project_id,
            capability="can_use_future_message_vault",
            detail="Your active package does not include governed future-message release.",
        )


def _service_access_context(context: dict[str, Any]) -> dict[str, str]:
    return {
        "requesting_workspace_role": _normalize(context.get("member_role")),
        "relationship_scope": _normalize(context.get("relationship_scope")),
        "link_status": _normalize(context.get("link_status")),
    }


def _allowed_vault_scopes(context: dict[str, Any]) -> tuple[str, ...]:
    if context.get("is_admin"):
        return ("personal", "household", "linked_family", "memorial", "organization")
    entitlements = context.get("resolved_entitlements") or {}
    allowed: list[str] = []
    if entitlements.get("can_use_personal_vault") or entitlements.get("can_use_household_vault"):
        allowed.extend(("personal", "memorial"))
    if entitlements.get("can_use_household_vault"):
        allowed.append("household")
    if entitlements.get("can_use_linked_household_vault"):
        allowed.append("linked_family")
    if entitlements.get("can_use_organization_records_vault"):
        allowed.append("organization")
    return tuple(dict.fromkeys(allowed))


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    detail = str(exc)
    normalized_detail = detail.lower()
    if "not found" in normalized_detail:
        code = status.HTTP_404_NOT_FOUND
    elif any(token in normalized_detail for token in ("access denied", "not available", "not released")):
        code = status.HTTP_403_FORBIDDEN
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=detail) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Vault Items
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_vault_item_route(
    payload: VaultItemCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(
        current_user,
        project_id=payload.project_id,
        vault_scope=payload.vault_scope,
    )
    _require_vault_role(context, write=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    _require_release_entitlements(
        current_user,
        project_id=project_id,
        release_state=payload.release_state,
        reveal_at=payload.reveal_at,
    )
    try:
        return create_vault_item(payload, user_id, authorized_project_id=project_id)
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.get("/items")
def list_vault_items_route(
    project_id: str = Query(...),
    vault_scope: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(
        current_user,
        project_id=project_id,
        vault_scope=vault_scope or "",
    )
    _require_vault_role(context)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return {
            "items": list_vault_items(
                project_id,
                user_id,
                vault_scope,
                authorized_project_id=authorized_project_id,
                **_service_access_context(context),
                allowed_vault_scopes=_allowed_vault_scopes(context),
            )
        }
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.get("/items/{item_id}")
def get_vault_item_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        item = get_vault_item(
            item_id,
            user_id,
            authorized_project_id=authorized_project_id,
            **_service_access_context(context),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    return item


@router.patch("/items/{item_id}")
def update_vault_item_route(
    item_id: str,
    payload: VaultItemUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    if "vault_scope" in payload.model_fields_set and payload.vault_scope:
        _resolve_vault_context(
            current_user,
            project_id=authorized_project_id,
            vault_scope=payload.vault_scope,
        )
    if {"release_state", "reveal_at"} & payload.model_fields_set:
        _require_release_entitlements(
            current_user,
            project_id=authorized_project_id,
            release_state=payload.release_state or _normalize(doc.get("release_state")),
            reveal_at=payload.reveal_at if "reveal_at" in payload.model_fields_set else None,
        )
    try:
        updated = update_vault_item(
            item_id,
            payload,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    return updated


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_item_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        delete_vault_item(item_id, user_id, authorized_project_id=authorized_project_id)
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Vault Collections
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/collections", status_code=status.HTTP_201_CREATED)
def create_vault_collection_route(
    payload: VaultCollectionCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(
        current_user,
        project_id=payload.project_id,
        vault_scope=payload.vault_scope,
    )
    _require_vault_role(context, write=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return create_vault_collection(payload, user_id, authorized_project_id=project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/collections")
def list_vault_collections_route(
    project_id: str = Query(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(current_user, project_id=project_id)
    _require_vault_role(context)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return {
            "items": list_vault_collections(
                project_id,
                user_id,
                authorized_project_id=authorized_project_id,
                requesting_workspace_role=_normalize(context.get("member_role")),
                link_status=_normalize(context.get("link_status")),
                allowed_vault_scopes=_allowed_vault_scopes(context),
            )
        }
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Vault Access Grants
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/items/{item_id}/grants", status_code=status.HTTP_201_CREATED)
def create_vault_access_grant_route(
    item_id: str,
    payload: VaultAccessGrantCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if payload.vault_item_id and payload.vault_item_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vault_item_id in payload must match path item_id.",
        )
    payload = payload.model_copy(update={"vault_item_id": item_id})
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return create_vault_access_grant(
            payload,
            user_id,
            item_id=item_id,
            authorized_project_id=authorized_project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.get("/items/{item_id}/grants")
def list_vault_access_grants_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return {
            "items": list_vault_access_grants(
                item_id,
                user_id,
                authorized_project_id=authorized_project_id,
            )
        }
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.patch("/items/{item_id}/grants/{grant_id}")
def update_vault_access_grant_route(
    item_id: str,
    grant_id: str,
    payload: VaultAccessGrantUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return update_vault_access_grant(
            item_id,
            grant_id,
            payload,
            user_id,
            authorized_project_id=project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.post("/items/{item_id}/grants/{grant_id}/revoke")
def revoke_vault_access_grant_route(
    item_id: str,
    grant_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return revoke_vault_access_grant(
            item_id,
            grant_id,
            user_id,
            authorized_project_id=project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.delete("/items/{item_id}/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_access_grant_route(
    item_id: str,
    grant_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        delete_vault_access_grant(
            item_id,
            grant_id,
            user_id,
            authorized_project_id=project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Vault Release Rules
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/items/{item_id}/release-rules", status_code=status.HTTP_201_CREATED)
def create_vault_release_rule_route(
    item_id: str,
    payload: VaultReleaseRuleCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if payload.vault_item_id and payload.vault_item_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vault_item_id in payload must match path item_id.",
        )
    payload = payload.model_copy(update={"vault_item_id": item_id})
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    _require_release_entitlements(
        current_user,
        project_id=authorized_project_id,
        trigger_type=payload.trigger_type,
    )
    try:
        return create_vault_release_rule(
            payload,
            user_id,
            item_id=item_id,
            authorized_project_id=authorized_project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.get("/items/{item_id}/release-rules")
def list_vault_release_rules_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return {
            "items": list_vault_release_rules(
                item_id,
                user_id,
                authorized_project_id=authorized_project_id,
            )
        }
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.patch("/items/{item_id}/release-rules/{rule_id}")
def update_vault_release_rule_route(
    item_id: str,
    rule_id: str,
    payload: VaultReleaseRuleUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    rule = _find_vault_release_rule_by_id(rule_id)
    if not rule or _normalize(rule.get("vault_item_id")) != item_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault release rule not found for this item.",
        )
    _require_release_entitlements(
        current_user,
        project_id=project_id,
        trigger_type=payload.trigger_type or _normalize(rule.get("trigger_type")),
    )
    try:
        return update_vault_release_rule(
            item_id,
            rule_id,
            payload,
            user_id,
            authorized_project_id=project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.post("/items/{item_id}/release-rules/{rule_id}/revoke")
def revoke_vault_release_rule_route(
    item_id: str,
    rule_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return revoke_vault_release_rule(
            item_id,
            rule_id,
            user_id,
            authorized_project_id=project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


@router.delete("/items/{item_id}/release-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_release_rule_route(
    item_id: str,
    rule_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True, mutation=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        delete_vault_release_rule(
            item_id,
            rule_id,
            user_id,
            authorized_project_id=project_id,
        )
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Vault Audit Events
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/items/{item_id}/audit")
def list_vault_audit_events_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(
        current_user,
        project_id=_normalize(doc.get("project_id")),
        vault_scope=_normalize(doc.get("vault_scope")),
    )
    _require_vault_role(context, sensitive=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return {
            "items": list_vault_audit_events(
                item_id,
                user_id,
                authorized_project_id=authorized_project_id,
            )
        }
    except (PermissionError, ValueError) as exc:
        _raise_service_error(exc)
