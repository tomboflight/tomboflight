from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies.auth import require_permission
from app.services.admin_control_service import (
    MAX_BULK_ACTION_LIMIT,
    admin_console_overview,
    assign_lane,
    assign_missing_lanes,
    customer_case_workspace,
    execute_case_action,
    enable_mint_review,
    generate_entitlement,
    link_order_to_project,
    link_unlinked_paid_orders,
    list_customer_cases,
    normalize_broken_package_records,
    refresh_mint_readiness,
    repair_missing_entitlements,
    repair_all_safe_records,
    repair_record,
    repair_selected_records,
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
    limit: int = Field(default=BULK_ACTION_DEFAULT_LIMIT, ge=1, le=MAX_BULK_ACTION_LIMIT)


class RepairSelectedPayload(BaseModel):
    project_ids: list[str] = Field(default_factory=list)
    order_ids: list[str] = Field(default_factory=list)


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


@router.get("/cases")
async def get_customer_cases(
    search: str = Query(default=""),
    queue: str = Query(default="customer_cases"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return await asyncio.to_thread(list_customer_cases, search=search, queue=queue, limit=limit)


@router.get("/cases/{case_id}")
async def get_customer_case_workspace(
    case_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return await asyncio.to_thread(customer_case_workspace, case_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{case_id}/actions/{action}")
async def run_customer_case_action(
    case_id: str,
    action: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return await asyncio.to_thread(execute_case_action, case_id=case_id, action=action)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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


@router.post("/bulk/normalize-broken-package-records")
def bulk_normalize_package_records(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return normalize_broken_package_records(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))


@router.post("/bulk/refresh-mint-readiness")
def bulk_refresh_mint_readiness(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return refresh_mint_readiness(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))


@router.post("/bulk/repair-selected-records")
def bulk_repair_selected_records(
    payload: RepairSelectedPayload,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return repair_selected_records(project_ids=payload.project_ids, order_ids=payload.order_ids)


@router.post("/bulk/repair-all-safe-records")
def bulk_repair_all_safe_records(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    return repair_all_safe_records(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
