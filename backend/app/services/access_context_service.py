from __future__ import annotations

from typing import Any

import logging

from app.database import get_database
from app.dependencies.auth import has_internal_admin_access
from app.services.experience_catalog_service import (
    derive_allowed_modules,
    derive_experience_mode,
    get_lane_chambers,
)
from app.services.project_entitlement_service import list_user_project_entitlements
from app.services.project_membership_service import list_accessible_project_ids
from app.services.workspace_access_service import resolve_workspace_context


logger = logging.getLogger(__name__)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _safe_database():
    try:
        return get_database()
    except RuntimeError:
        return None


def _current_user_id(user: dict[str, Any]) -> str:
    return _normalize(user.get("id") or user.get("_id") or user.get("user_id"))


def _current_user_email(user: dict[str, Any]) -> str:
    return _normalize_email(user.get("email"))


def _current_user_role(user: dict[str, Any]) -> str:
    return _normalize(user.get("role")) or "user"


def _current_user_status(user: dict[str, Any]) -> str:
    return _normalize(user.get("status")) or "active"


def _current_user_legal_acceptance(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_version": user.get("policy_version"),
        "terms_accepted_at": user.get("terms_accepted_at"),
        "privacy_accepted_at": user.get("privacy_accepted_at"),
        "eligibility_attested_at": user.get("eligibility_attested_at"),
    }


def resolve_default_project_id(current_user: dict[str, Any]) -> str | None:
    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)

    # Project memberships are the source of truth for invited customers
    # (co-owner, family manager, contributor, viewer, linked relative).
    # Use them first so invited users retain durable workspace context.
    if user_id or user_email:
        try:
            accessible_ids = list_accessible_project_ids(
                user_id=user_id,
                email=user_email,
                active_only=True,
            )
        except Exception as exc:
            logger.warning(
                "Unable to load project memberships for user %s: %s",
                user_id or user_email,
                exc,
            )
            accessible_ids = []
        for project_id in accessible_ids:
            normalized = _normalize(project_id)
            if normalized:
                return normalized

    if user_id:
        try:
            entitlements = list_user_project_entitlements(
                user_id,
                email=user_email,
                active_only=True,
            )
        except RuntimeError as exc:
            logger.warning("Unable to load project entitlements for user %s: %s", user_id, exc)
            entitlements = []
        except ValueError as exc:
            logger.warning("Invalid project entitlement data for user %s: %s", user_id, exc)
            entitlements = []
        for entitlement in entitlements:
            project_id = _normalize(entitlement.get("project_id"))
            if project_id:
                return project_id

    db = _safe_database()
    if db is None:
        return None

    query: dict[str, Any] = {}
    if has_internal_admin_access(current_user):
        project = db["projects"].find_one(sort=[("updated_at", -1), ("created_at", -1)])
        return _normalize((project or {}).get("_id")) or None

    filters: list[dict[str, Any]] = []
    if user_id:
        filters.append({"owner_user_id": user_id})
    if user_email:
        filters.append({"owner_email": user_email})
    if not filters:
        return None

    query["$or"] = filters
    project = db["projects"].find_one(query, sort=[("updated_at", -1), ("created_at", -1)])
    return _normalize((project or {}).get("_id")) or None


def build_access_context(
    current_user: dict[str, Any],
    *,
    project_id: str = "",
) -> dict[str, Any]:
    resolved_project_id = _normalize(project_id) or (resolve_default_project_id(current_user) or "")
    workspace_context: dict[str, Any] = {}

    if resolved_project_id:
        try:
            workspace_context = resolve_workspace_context(
                current_user,
                project_id=resolved_project_id,
            )
        except Exception as exc:
            logger.warning(
                "Unable to resolve workspace context for user %s project %s: %s",
                _current_user_id(current_user) or _current_user_email(current_user),
                resolved_project_id,
                exc,
            )
            workspace_context = {}

    project = workspace_context.get("project") or {}
    family = workspace_context.get("family") or {}
    entitlements = workspace_context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"

    active_entitlements = sorted(
        key
        for key, enabled in entitlements.items()
        if str(key).startswith("can_") and bool(enabled)
    )
    if workspace_context.get("is_admin"):
        active_entitlements = sorted(set(active_entitlements + ["admin.access"]))

    allowed_modules = derive_allowed_modules(package_lane, entitlements)
    if workspace_context.get("is_admin"):
        allowed_modules = list(dict.fromkeys(allowed_modules + ["admin_workspace"]))

    return {
        "user_id": _current_user_id(current_user),
        "email": _current_user_email(current_user),
        "role": _current_user_role(current_user),
        "status": _current_user_status(current_user),
        "package_lane": package_lane,
        "active_project_id": _normalize(project.get("_id")) or resolved_project_id or None,
        "active_family_id": _normalize(family.get("_id")) or None,
        "active_entitlements": active_entitlements,
        "project_permissions": active_entitlements,
        "allowed_experience_modules": allowed_modules,
        "experience_mode": derive_experience_mode(package_lane),
        "legal_acceptance": _current_user_legal_acceptance(current_user),
    }


def describe_project_experience_lane(
    current_user: dict[str, Any],
    project_id: str,
) -> dict[str, Any]:
    context = resolve_workspace_context(current_user, project_id=project_id)
    project = context.get("project") or {}
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"

    return {
        "project_id": _normalize(project.get("_id")) or project_id,
        "project_lane": package_lane,
        "package_code": _normalize(
            entitlements.get("package_code") or project.get("package_code") or project.get("package_slug")
        ),
        "package_name": _normalize(
            entitlements.get("display_name") or project.get("package_name") or "Tomb of Light Project"
        ),
        "experience_mode": derive_experience_mode(package_lane),
        "allowed_chambers": get_lane_chambers(package_lane),
        "unlocked_modules": derive_allowed_modules(package_lane, entitlements),
    }
