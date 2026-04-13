from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database
from app.dependencies.auth import (
    get_current_user,
)
from app.services.workspace_access_service import require_workspace_capability
from app.services.tree_service import (
    get_family_tree,
    get_filtered_family_tree,
    get_linked_family_tree,
)

router = APIRouter(prefix="/tree", tags=["Tree"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_email(user: dict[str, Any]) -> str:
    raw_email = user.get("email")
    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user email is missing.",
        )
    return str(raw_email).strip().lower()


def _current_user_display_name(user: dict[str, Any]) -> str:
    raw_name = user.get("full_name") or user.get("name") or ""
    return str(raw_name).strip()


@router.get("/{family_id}")
def get_tree(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_build_family_tree",),
        detail="Your active package does not include family tree access.",
    )
    resolved_family_id = str(context["family"].get("_id"))

    tree = get_family_tree(resolved_family_id)

    if not tree["members"] and not tree["nodes"] and not tree["relationships"]:
        raise HTTPException(status_code=404, detail="Family tree not found.")

    return tree


@router.get("/{family_id}/verified")
def get_verified_tree(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_build_family_tree",),
        detail="Your active package does not include family tree access.",
    )
    tree = get_filtered_family_tree(str(context["family"].get("_id")), "verified")
    return tree


@router.get("/{family_id}/narrative")
def get_narrative_tree(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_build_family_tree",),
        detail="Your active package does not include family tree access.",
    )
    tree = get_filtered_family_tree(str(context["family"].get("_id")), "narrative")
    return tree


@router.get("/{family_id}/private")
def get_private_tree(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_build_family_tree",),
        detail="Your active package does not include family tree access.",
    )
    tree = get_filtered_family_tree(str(context["family"].get("_id")), "private")
    return tree


@router.get("/{family_id}/linked")
def get_linked_tree(
    family_id: str,
    mode: str = "default",
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_link_households",),
        detail="Your active package does not include linked family graph access.",
    )
    resolved_family_id = str(context["family"].get("_id"))
    normalized_mode = str(mode or "default").strip().lower()
    if normalized_mode not in {"default", "verified", "narrative", "private"}:
        raise HTTPException(status_code=400, detail="Invalid linked tree mode.")
    return get_linked_family_tree(resolved_family_id, normalized_mode)
