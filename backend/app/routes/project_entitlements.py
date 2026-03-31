from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies.auth import INTERNAL_ADMIN_KEYS, get_current_user, require_admin
from app.services.project_entitlement_service import (
    get_project_entitlement,
    get_upgrade_quote_for_project,
    list_project_entitlements,
    list_user_project_entitlements,
    upsert_project_entitlement,
)

router = APIRouter(prefix="/project-entitlements", tags=["Project Entitlements"])

INTERNAL_ADMIN_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
}


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
    role = str(user.get("role") or "").strip().lower()
    access_tier = str(user.get("access_tier") or "").strip().lower()
    department_role = str(user.get("department_role") or "").strip().lower()

    return any(
        value in INTERNAL_ADMIN_KEYS
        for value in (role, access_tier, department_role)
    )


@router.post("/apply")
def apply_project_entitlement(
    payload: ApplyProjectEntitlementPayload,
    current_user: dict[str, Any] = Depends(require_admin),
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

    current_user_id = _current_user_id(current_user)

    if not _is_admin(current_user) and entitlement.get("user_id") != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this project entitlement.",
        )

    return entitlement


@router.get("/my-active")
def list_my_project_entitlements(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    current_user_id = _current_user_id(current_user)
    return {
        "items": list_user_project_entitlements(current_user_id, active_only=True),
    }


@router.get("/admin/list")
def list_project_entitlements_admin(
    limit: int = 100,
    active_only: bool = False,
    search: str = "",
    current_user: dict[str, Any] = Depends(require_admin),
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

    current_user_id = _current_user_id(current_user)

    if not _is_admin(current_user) and entitlement.get("user_id") != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this upgrade quote.",
        )

    try:
        return get_upgrade_quote_for_project(project_id, to_package_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
