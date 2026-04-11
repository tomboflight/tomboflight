from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies.auth import require_permission
from app.services.admin_control_service import (
    admin_console_overview,
    assign_lane,
    assign_missing_lanes,
    enable_mint_review,
    generate_entitlement,
    link_order_to_project,
    link_unlinked_paid_orders,
    repair_missing_entitlements,
    repair_record,
    project_workspace_snapshot,
    run_readiness_check,
    sync_package,
)

router = APIRouter(prefix="/admin/control-center", tags=["Admin Control Center"])
BULK_ACTION_DEFAULT_LIMIT = 500


class SyncPackagePayload(BaseModel):
    order_id: str = Field(default="")


class LinkOrderPayload(BaseModel):
    project_id: str = Field(default="")


class GenerateEntitlementPayload(BaseModel):
    order_id: str = Field(default="")
    force: bool = True


class EnableMintReviewPayload(BaseModel):
    order_id: str = Field(default="")


class RepairRecordPayload(BaseModel):
    order_id: str = Field(default="")


class BulkRepairPayload(BaseModel):
    limit: int = Field(default=BULK_ACTION_DEFAULT_LIMIT, ge=1, le=5000)


@router.get("/overview")
def get_admin_control_overview(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return admin_console_overview(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/projects/{project_id}/workspace")
def get_project_workspace_snapshot(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return project_workspace_snapshot(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/projects/{project_id}/sync-package")
def sync_project_package(
    project_id: str,
    payload: SyncPackagePayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return sync_package(project_id=project_id, order_id=(payload.order_id if payload else ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects/{project_id}/assign-lane")
def assign_project_lane(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return assign_lane(project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/orders/{order_id}/link-project")
def link_project_to_order(
    order_id: str,
    payload: LinkOrderPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return link_order_to_project(
            order_id=order_id,
            project_id=(payload.project_id if payload else ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects/{project_id}/generate-entitlement")
def generate_project_entitlement(
    project_id: str,
    payload: GenerateEntitlementPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return generate_entitlement(
            project_id=project_id,
            order_id=(payload.order_id if payload else ""),
            force=bool(payload.force) if payload else True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/projects/{project_id}/readiness-check")
def get_project_readiness(
    project_id: str,
    order_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return run_readiness_check(project_id=project_id, order_id=order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/projects/{project_id}/enable-mint-review")
def queue_project_for_mint_review(
    project_id: str,
    payload: EnableMintReviewPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return enable_mint_review(project_id=project_id, order_id=(payload.order_id if payload else ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/projects/{project_id}/repair-record")
def repair_project_record(
    project_id: str,
    payload: RepairRecordPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return repair_record(project_id=project_id, order_id=(payload.order_id if payload else ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/bulk/repair-missing-entitlements")
def bulk_repair_entitlements(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return repair_missing_entitlements(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))


@router.post("/bulk/assign-missing-lanes")
def bulk_assign_lanes(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return assign_missing_lanes(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))


@router.post("/bulk/link-unlinked-paid-orders")
def bulk_link_paid_orders(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return link_unlinked_paid_orders(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
