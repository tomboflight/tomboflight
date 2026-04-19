from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
    require_permission,
)
from app.core.package_catalog import get_package, get_package_catalog
from app.database import get_database
from app.services.project_membership_service import get_project_access_snapshot
from app.services.entitlement_service import resolve_project_entitlements
from app.services.project_entitlement_service import (
    get_project_entitlement,
    get_upgrade_quote_for_project,
    list_project_entitlements,
    list_user_project_entitlements,
    upsert_project_entitlement,
)

router = APIRouter(prefix="/project-entitlements", tags=["Project Entitlements"])

class ApplyProjectEntitlementPayload(BaseModel):
    project_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    package_code: str = Field(min_length=1)
    active_addons: list[str] = Field(default_factory=list)
    maintenance_plan: str = Field(default="monthly")
    delivered_at: datetime | None = None
    status: str = Field(default="active")


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _is_admin(user: dict[str, Any]) -> bool:
    return has_internal_admin_access(user)


def _assert_workspace_access(project_id: str, current_user: dict[str, Any]) -> None:
    db = get_database()
    project_stub = None
    if db is not None and ObjectId.is_valid(project_id):
        project_stub = db["projects"].find_one({"_id": ObjectId(project_id)})
    project_stub = project_stub or {"_id": project_id}
    snapshot = get_project_access_snapshot(
        project_stub,
        user_id=_current_user_id(current_user),
        email=str(current_user.get("email") or "").strip().lower(),
    )
    if not snapshot.get("accessible"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this project entitlement.",
        )


@router.post("/apply")
def apply_project_entitlement(
    payload: ApplyProjectEntitlementPayload,
    current_user: dict[str, Any] = Depends(require_permission("admin.entitlements.write")),
):
    try:
        return upsert_project_entitlement(
            project_id=payload.project_id,
            user_id=payload.user_id,
            package_code=payload.package_code,
            active_addons=payload.active_addons,
            maintenance_plan=payload.maintenance_plan,
            delivered_at=payload.delivered_at,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/project/{project_id}")
def get_project_entitlement_route(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    entitlement = get_project_entitlement(project_id)
    if not entitlement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project entitlement not found.",
        )

    if not _is_admin(current_user):
        _assert_workspace_access(project_id, current_user)

    return entitlement


@router.get("/my-active")
def list_my_project_entitlements(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    current_user_id = _current_user_id(current_user)
    current_user_email = str(current_user.get("email") or "").strip().lower()
    return {
        "items": list_user_project_entitlements(
            current_user_id,
            email=current_user_email,
            active_only=True,
        ),
    }


@router.get("/admin/list")
def list_project_entitlements_admin(
    limit: int = 100,
    active_only: bool = False,
    search: str = "",
    current_user: dict[str, Any] = Depends(require_permission("admin.entitlements.read")),
):
    del current_user
    return {
        "items": list_project_entitlements(
            active_only=active_only,
            limit=limit,
            search=search,
        )
    }


@router.get("/upgrade-quote/{project_id}/{to_package_code}")
def get_project_upgrade_quote_route(
    project_id: str,
    to_package_code: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    entitlement = get_project_entitlement(project_id)
    if not entitlement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project entitlement not found.",
        )

    if not _is_admin(current_user):
        _assert_workspace_access(project_id, current_user)

    try:
        return get_upgrade_quote_for_project(project_id, to_package_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/project/{project_id}/package-summary")
def get_package_summary_route(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    entitlement = get_project_entitlement(project_id)
    if not entitlement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project entitlement not found.",
        )

    if not _is_admin(current_user):
        _assert_workspace_access(project_id, current_user)

    package_code = str(entitlement.get("package_code") or "").strip()
    active_addons = list(entitlement.get("active_addons") or [])

    try:
        resolved = resolve_project_entitlements(package_code, active_addons)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not resolve entitlements: {exc}",
        ) from exc

    package_data = get_package(package_code) or {}
    upgrade_targets: list[str] = list(package_data.get("upgrade_targets") or [])
    all_packages = get_package_catalog()

    upgrade_options = []
    for target_code in upgrade_targets:
        target_pkg = all_packages.get(target_code)
        if target_pkg:
            display_name = target_pkg.get("display_name", target_code)
            upgrade_options.append({
                "package_code": target_code,
                "display_name": display_name,
                "description": target_pkg.get("description") or f"Upgrade to {display_name}",
            })

    return {
        "package": {
            "name": resolved.get("display_name") or entitlement.get("package_name") or package_code,
            "lane": resolved.get("package_lane") or entitlement.get("package_lane") or "",
            "active_addons": active_addons,
            "maintenance_status": entitlement.get("maintenance_status") or "not_started",
        },
        "capabilities": {
            "build_family_tree": bool(resolved.get("can_build_family_tree", False)),
            "link_households": bool(resolved.get("can_link_households", False)),
            "use_narration": bool(resolved.get("can_use_narration", False)),
            "use_certificates": bool(resolved.get("can_use_lineage_certificate", False)),
            "storage_gb": resolved.get("max_storage_gb", 0),
            "max_uploads": resolved.get("max_uploads", 0),
            "max_zoom_layers": resolved.get("max_zoom_layers", 0),
            "max_members": resolved.get("max_members", 0),
        },
        "sharing": {
            "private_account": "Personal vault items, private living-person records, private notes, unapproved uploads",
            "your_household": "Family tree visible to household members",
            "approved_linked_families": "Shared lineage visible to linked households (if enabled)",
            "public_memorial": "Public memorial content only (deceased/memorial nodes)",
        },
        "not_shared": [
            "Personal vault items",
            "Private living-person records",
            "Private notes",
            "Unapproved uploads",
        ],
        "upgrade_options": upgrade_options,
    }
