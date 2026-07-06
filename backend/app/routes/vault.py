from __future__ import annotations

from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_database
from app.dependencies.auth import get_current_user
from app.schemas.vault import (
    VaultAccessGrantCreate,
    VaultCollectionCreate,
    VaultItemCreate,
    VaultItemUpdate,
    VaultReleaseRuleCreate,
)
from app.services.vault_service import (
    create_vault_access_grant,
    create_vault_collection,
    create_vault_item,
    create_vault_release_rule,
    delete_vault_item,
    get_vault_item,
    list_vault_access_grants,
    list_vault_audit_events,
    list_vault_collections,
    list_vault_items,
    list_vault_release_rules,
    update_vault_item,
)
from app.services.workspace_access_service import (
    require_workspace_capability,
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


HOUSEHOLD_VAULT_CAPABILITIES = ("can_use_household_vault",)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _find_vault_item_by_id(item_id: str) -> dict[str, Any] | None:
    db = get_database()
    if ObjectId.is_valid(item_id):
        return db["vault_items"].find_one({"_id": ObjectId(item_id)})
    return db["vault_items"].find_one({"_id": item_id})


def _resolve_vault_context(
    current_user: dict[str, Any],
    *,
    project_id: str,
) -> dict[str, Any]:
    return require_workspace_capability(
        current_user,
        project_id=project_id,
        capabilities=HOUSEHOLD_VAULT_CAPABILITIES,
        detail="Your active package does not include private household vault access.",
    )


def _require_vault_role(context: dict[str, Any], *, write: bool = False, sensitive: bool = False) -> None:
    if sensitive:
        allowed_roles = ("billing_owner", "co_owner", "family_manager")
        detail = "Your role cannot manage vault grants or release rules."
    elif write:
        allowed_roles = ("billing_owner", "co_owner", "family_manager", "contributor")
        detail = "Your role is read-only for vault updates."
    else:
        allowed_roles = ("billing_owner", "co_owner", "family_manager", "contributor", "viewer")
        detail = "Your role cannot access vault items."
    require_workspace_member_role(context, allowed_roles=allowed_roles, detail=detail)


# ─────────────────────────────────────────────────────────────────────────────
# Vault Items
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_vault_item_route(
    payload: VaultItemCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(current_user, project_id=payload.project_id)
    _require_vault_role(context, write=True)
    project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return create_vault_item(payload, user_id, authorized_project_id=project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/items")
def list_vault_items_route(
    project_id: str = Query(...),
    vault_scope: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(current_user, project_id=project_id)
    _require_vault_role(context)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return {
            "items": list_vault_items(
                project_id,
                user_id,
                vault_scope,
                authorized_project_id=authorized_project_id,
            )
        }
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/items/{item_id}")
def get_vault_item_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
    _require_vault_role(context)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        item = get_vault_item(item_id, user_id, authorized_project_id=authorized_project_id)
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
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
    _require_vault_role(context, write=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        updated = update_vault_item(
            item_id,
            payload,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

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
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
    _require_vault_role(context, sensitive=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        delete_vault_item(item_id, user_id, authorized_project_id=authorized_project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Vault Collections
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/collections", status_code=status.HTTP_201_CREATED)
def create_vault_collection_route(
    payload: VaultCollectionCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    context = _resolve_vault_context(current_user, project_id=payload.project_id)
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
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
    _require_vault_role(context, sensitive=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return create_vault_access_grant(
            payload,
            user_id,
            item_id=item_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/items/{item_id}/grants")
def list_vault_access_grants_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
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
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
    _require_vault_role(context, sensitive=True)
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    try:
        return create_vault_release_rule(
            payload,
            user_id,
            item_id=item_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/items/{item_id}/release-rules")
def list_vault_release_rules_route(
    item_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    doc = _find_vault_item_by_id(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault item not found.")
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
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
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
    context = _resolve_vault_context(current_user, project_id=_normalize(doc.get("project_id")))
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
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
