from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies.auth import require_any_permission, require_permission, require_super_admin
from app.services.auth_service import admin_issue_password_reset
from app.services.audit_log_service import write_audit_log
from app.services.admin_control_service import (
    MAX_BULK_ACTION_LIMIT,
    admin_control_access_profile,
    admin_control_action_allowed,
    admin_control_bulk_action_allowed,
    admin_control_queue_allowed,
    admin_console_overview,
    assign_lane,
    assign_missing_lanes,
    customer_case_workspace,
    execute_case_action,
    export_operations_report,
    enable_mint_review,
    generate_entitlement,
    link_order_to_project,
    link_unlinked_paid_orders,
    list_customer_cases,
    normalize_broken_package_records,
    refresh_mint_readiness,
    repair_project_mint_status,
    repair_missing_entitlements,
    repair_all_safe_records,
    repair_record,
    repair_selected_records,
    super_admin_apply_package_change,
    super_admin_apply_user_state_action,
    super_admin_repair_case_action,
    super_admin_list_users,
    super_admin_preview_package_change,
    super_admin_update_user,
    resync_current_mint_receipt,
    project_workspace_snapshot,
    run_readiness_check,
    sync_package,
)

router = APIRouter(prefix="/admin/control-center", tags=["Admin Control Center"])
BULK_ACTION_DEFAULT_LIMIT = 500


def _string_value(value: Any) -> str:
    return str(value or "").strip()


def _audit_bulk_action(
    *,
    current_user: dict[str, Any],
    action: str,
    result_payload: dict[str, Any],
) -> None:
    try:
        first_name = _string_value(current_user.get("first_name"))
        last_name = _string_value(current_user.get("last_name"))
        actor_name = _string_value(current_user.get("full_name")) or " ".join(
            [first_name, last_name]
        ).strip()
        write_audit_log(
            actor_user_id=_string_value(
                current_user.get("_id") or current_user.get("id") or current_user.get("user_id")
            )
            or None,
            actor_email=_string_value(current_user.get("email")).lower() or None,
            actor_name=actor_name or None,
            action=f"admin_control_center.bulk.{action}",
            target_type="bulk_repair",
            target_id=action,
            after=result_payload,
            context={"admin_surface": "customer_operations_workspace"},
            result="success",
        )
    except Exception:
        return


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


class SuperAdminUserUpdatePayload(BaseModel):
    email: str | None = None
    full_name: str | None = None
    phone_number: str | None = None
    birthday: str | None = None
    mailing_address: str | None = None
    status: str | None = None
    role: str | None = None
    access_tier: str | None = None
    department_role: str | None = None


class SuperAdminUserStateActionPayload(BaseModel):
    action: str = Field(min_length=1)


class SuperAdminPackageChangePayload(BaseModel):
    package_code: str = Field(min_length=1)
    project_lane: str = Field(default="")
    order_status: str = Field(default="")


class SuperAdminRepairPayload(BaseModel):
    action: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    relationship_id: str | None = None
    member_id: str | None = None
    source_member_id: str | None = None
    target_member_id: str | None = None
    family_id: str | None = None
    child_member_id: str | None = None
    parent_member_id: str | None = None
    parent_first_name: str | None = None
    parent_last_name: str | None = None
    parent_birth_year: int | None = None
    relationship_type: str | None = None
    notes: str | None = None
    invite_id: str | None = None
    invite_email: str | None = None
    membership_id: str | None = None
    member_role: str | None = None
    relationship_scope: str | None = None
    privacy_scope: str | None = None
    status: str | None = None
    confirm_destructive: bool = False


def _current_user_id(current_user: dict[str, Any]) -> str:
    return _string_value(current_user.get("_id") or current_user.get("id") or current_user.get("user_id"))


def _current_user_display(current_user: dict[str, Any]) -> str:
    full_name = _string_value(current_user.get("full_name"))
    if full_name:
        return full_name
    first_name = _string_value(current_user.get("first_name"))
    last_name = _string_value(current_user.get("last_name"))
    return " ".join([first_name, last_name]).strip()


def _assert_bulk_action_allowed(current_user: dict[str, Any], action: str) -> None:
    if admin_control_bulk_action_allowed(current_user, action):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Admin control bulk action '{action}' is not permitted for this role.",
    )


@router.get("/access-profile")
def get_admin_control_access_profile(
    current_user: dict[str, Any] = Depends(require_any_permission(["admin.control.view", "admin.analytics.read"])),
):
    return admin_control_access_profile(current_user)


@router.get("/overview")
def get_admin_control_overview(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(require_any_permission(["admin.control.view", "admin.analytics.read"])),
):
    del current_user
    try:
        return admin_console_overview(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/ops-reports/export")
def get_operations_report_export(
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    if not admin_control_queue_allowed(current_user, "ops_reports"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operations report export is not permitted for this role.",
        )
    return export_operations_report()


@router.get("/cases")
async def get_customer_cases(
    search: str = Query(default=""),
    queue: str = Query(default="customer_cases"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    if not admin_control_queue_allowed(current_user, queue):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin control queue '{queue}' is not permitted for this role.",
        )
    return await asyncio.to_thread(
        list_customer_cases,
        search=search,
        queue=queue,
        limit=limit,
        current_user=current_user,
    )


@router.get("/cases/{case_id}")
async def get_customer_case_workspace(
    case_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    try:
        return await asyncio.to_thread(customer_case_workspace, case_id, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/cases/{case_id}/actions/{action}")
async def run_customer_case_action(
    case_id: str,
    action: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    if not admin_control_action_allowed(current_user, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin control action '{action}' is not permitted for this role.",
        )
    try:
        return await asyncio.to_thread(
            execute_case_action,
            case_id=case_id,
            action=action,
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/projects/{project_id}/workspace")
def get_project_workspace_snapshot(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    try:
        return project_workspace_snapshot(project_id, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/projects/{project_id}/sync-package")
def sync_project_package(
    project_id: str,
    payload: SyncPackagePayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.write")),
):
    del current_user
    try:
        return sync_package(project_id=project_id, order_id=(payload.order_id if payload else ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects/{project_id}/assign-lane")
def assign_project_lane(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.write")),
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
    current_user: dict[str, Any] = Depends(require_permission("admin.control.billing")),
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
    current_user: dict[str, Any] = Depends(require_permission("admin.control.billing")),
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
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
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
    current_user: dict[str, Any] = Depends(
        require_any_permission(["admin.control.mint", "admin.control.mint.readiness"])
    ),
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
    current_user: dict[str, Any] = Depends(require_permission("admin.control.write")),
):
    del current_user
    try:
        return repair_record(project_id=project_id, order_id=(payload.order_id if payload else ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects/{project_id}/repair-mint-status")
def repair_project_mint_state(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.mint")),
):
    del current_user
    try:
        return repair_project_mint_status(project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects/{project_id}/resync-mint-receipt")
def resync_project_mint_receipt(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.mint")),
):
    del current_user
    try:
        return resync_current_mint_receipt(project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/bulk/repair-missing-entitlements")
def bulk_repair_entitlements(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    _assert_bulk_action_allowed(current_user, "repair-missing-entitlements")
    result = repair_missing_entitlements(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
    _audit_bulk_action(current_user=current_user, action="repair_missing_entitlements", result_payload=result)
    return result


@router.post("/repairs/missing-entitlements")
def repair_missing_entitlements_route(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    return bulk_repair_entitlements(payload=payload, current_user=current_user)


@router.post("/bulk/assign-missing-lanes")
def bulk_assign_lanes(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    _assert_bulk_action_allowed(current_user, "assign-missing-lanes")
    result = assign_missing_lanes(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
    _audit_bulk_action(current_user=current_user, action="assign_missing_lanes", result_payload=result)
    return result


@router.post("/repairs/missing-lanes")
def repair_missing_lanes_route(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    return bulk_assign_lanes(payload=payload, current_user=current_user)


@router.post("/bulk/link-unlinked-paid-orders")
def bulk_link_paid_orders(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    _assert_bulk_action_allowed(current_user, "link-unlinked-paid-orders")
    result = link_unlinked_paid_orders(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
    _audit_bulk_action(current_user=current_user, action="link_unlinked_paid_orders", result_payload=result)
    return result


@router.post("/repairs/unlinked-paid-orders")
def link_unlinked_paid_orders_route(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    return bulk_link_paid_orders(payload=payload, current_user=current_user)


@router.post("/bulk/normalize-broken-package-records")
def bulk_normalize_package_records(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    _assert_bulk_action_allowed(current_user, "normalize-broken-package-records")
    result = normalize_broken_package_records(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
    _audit_bulk_action(current_user=current_user, action="normalize_broken_package_records", result_payload=result)
    return result


@router.post("/bulk/refresh-mint-readiness")
def bulk_refresh_mint_readiness(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    _assert_bulk_action_allowed(current_user, "refresh-mint-readiness")
    result = refresh_mint_readiness(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
    _audit_bulk_action(current_user=current_user, action="refresh_mint_readiness", result_payload=result)
    return result


@router.post("/bulk/repair-selected-records")
def bulk_repair_selected_records(
    payload: RepairSelectedPayload,
    current_user: dict[str, Any] = Depends(require_any_permission(["admin.control.write", "admin.control.billing"])),
):
    _assert_bulk_action_allowed(current_user, "repair-selected-records")
    result = repair_selected_records(project_ids=payload.project_ids, order_ids=payload.order_ids)
    _audit_bulk_action(current_user=current_user, action="repair_selected_records", result_payload=result)
    return result


@router.post("/bulk/repair-all-safe-records")
def bulk_repair_all_safe_records(
    payload: BulkRepairPayload | None = None,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    _assert_bulk_action_allowed(current_user, "repair-all-safe-records")
    result = repair_all_safe_records(limit=(payload.limit if payload else BULK_ACTION_DEFAULT_LIMIT))
    _audit_bulk_action(current_user=current_user, action="repair_all_safe_records", result_payload=result)
    return result


@router.get("/super-admin/users")
def super_admin_users_index(
    search: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    del current_user
    return super_admin_list_users(search=search, limit=limit)


@router.patch("/super-admin/users/{user_id}")
def super_admin_patch_user(
    user_id: str,
    payload: SuperAdminUserUpdatePayload,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    try:
        return super_admin_update_user(
            user_id=user_id,
            payload=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/super-admin/users/{user_id}/status-action")
def super_admin_user_status_action(
    user_id: str,
    payload: SuperAdminUserStateActionPayload,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    try:
        return super_admin_apply_user_state_action(
            user_id=user_id,
            action=payload.action,
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/super-admin/users/{user_id}/password-reset")
def super_admin_user_password_reset(
    user_id: str,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    try:
        return admin_issue_password_reset(
            user_id,
            admin_user_id=_current_user_id(current_user),
            admin_display=_current_user_display(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/super-admin/projects/{project_id}/package-change/preview")
def super_admin_preview_project_package_change(
    project_id: str,
    payload: SuperAdminPackageChangePayload,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    del current_user
    try:
        return super_admin_preview_package_change(
            project_id=project_id,
            package_code=payload.package_code,
            project_lane=payload.project_lane,
            order_status=payload.order_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/super-admin/projects/{project_id}/package-change/apply")
def super_admin_apply_project_package_change(
    project_id: str,
    payload: SuperAdminPackageChangePayload,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    try:
        return super_admin_apply_package_change(
            project_id=project_id,
            package_code=payload.package_code,
            project_lane=payload.project_lane,
            order_status=payload.order_status,
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/super-admin/cases/{case_id}/repair")
def super_admin_case_repair(
    case_id: str,
    payload: SuperAdminRepairPayload,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    try:
        return super_admin_repair_case_action(
            case_id=case_id,
            action=payload.action,
            payload=payload.model_dump(exclude_none=True),
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
