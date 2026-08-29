from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.admin_permission_registry import is_canonical_ceo_email
from app.database import DatabaseUnavailableError
from app.dependencies.auth import require_any_permission, require_permission, require_super_admin
from app.services.continuity_runtime_service import (
    approve_operation,
    build_project_continuity_snapshot,
    canonical_officer_role,
    close_operation,
    execute_governed_action,
    execute_operation,
    get_operation,
    list_operation_events,
    list_operations,
    reject_operation,
    request_operation,
    runtime_status,
)


router = APIRouter(prefix="/admin/control-center/kernel", tags=["Admin Continuity Runtime"])


class OperationRequestPayload(BaseModel):
    action: str = Field(min_length=1)
    target: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=3)
    idempotency_key: str = Field(min_length=8)


class OperationApprovalPayload(BaseModel):
    approval_reason: str = Field(min_length=3)
    solo_founder_override_acknowledged: bool = False


class OperationRejectionPayload(BaseModel):
    rejection_reason: str = Field(min_length=3)


class GovernedExecutionPayload(OperationRequestPayload):
    confirmed: bool = False
    solo_founder_override_acknowledged: bool = False


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, DatabaseUnavailableError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _assert_canonical_ceo(current_user: dict[str, Any]) -> None:
    if is_canonical_ceo_email(current_user.get("email")):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Governed one-step execution is restricted to the canonical CEO Master Administrator.",
    )


def _write_dependency():
    return require_any_permission(
        [
            "admin.control.write",
            "admin.control.billing",
            "admin.control.mint",
            "admin.entitlements.write",
        ]
    )


@router.get("/status")
def get_continuity_runtime_status(
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    try:
        payload = runtime_status()
        payload["current_actor_role"] = canonical_officer_role(current_user) or None
        payload["one_step_execution_allowed"] = is_canonical_ceo_email(
            current_user.get("email")
        )
        return payload
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/projects/{project_id}/snapshot")
def get_project_kernel_snapshot(
    project_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    del current_user
    try:
        return build_project_continuity_snapshot(project_id)
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/operations")
def get_continuity_operations(
    operation_state: str = Query(default="", alias="state"),
    target_id: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    del current_user
    try:
        return list_operations(state=operation_state, target_id=target_id, limit=limit)
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/operations/{operation_id}")
def get_continuity_operation(
    operation_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    del current_user
    try:
        return get_operation(operation_id)
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/operations/{operation_id}/events")
def get_continuity_operation_events(
    operation_id: str,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.view")),
):
    del current_user
    try:
        return list_operation_events(operation_id)
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/operations", status_code=status.HTTP_201_CREATED)
def create_continuity_operation(
    payload: OperationRequestPayload,
    current_user: dict[str, Any] = Depends(_write_dependency()),
):
    try:
        return request_operation(
            action=payload.action,
            target=payload.target,
            parameters=payload.parameters,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            actor=current_user,
        )
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/operations/{operation_id}/approve")
def approve_continuity_operation(
    operation_id: str,
    payload: OperationApprovalPayload,
    current_user: dict[str, Any] = Depends(_write_dependency()),
):
    try:
        return approve_operation(
            operation_id,
            approval_reason=payload.approval_reason,
            actor=current_user,
            solo_founder_override_acknowledged=payload.solo_founder_override_acknowledged,
        )
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/operations/{operation_id}/reject")
def reject_continuity_operation(
    operation_id: str,
    payload: OperationRejectionPayload,
    current_user: dict[str, Any] = Depends(_write_dependency()),
):
    try:
        return reject_operation(
            operation_id,
            rejection_reason=payload.rejection_reason,
            actor=current_user,
        )
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/operations/{operation_id}/execute")
def execute_continuity_operation(
    operation_id: str,
    current_user: dict[str, Any] = Depends(_write_dependency()),
):
    try:
        return execute_operation(operation_id, actor=current_user)
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/operations/{operation_id}/close")
def close_continuity_operation(
    operation_id: str,
    current_user: dict[str, Any] = Depends(_write_dependency()),
):
    try:
        return close_operation(operation_id, actor=current_user)
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/execute")
def execute_continuity_action_as_ceo(
    payload: GovernedExecutionPayload,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    _assert_canonical_ceo(current_user)
    try:
        return execute_governed_action(
            action=payload.action,
            target=payload.target,
            parameters=payload.parameters,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            actor=current_user,
            confirmed=payload.confirmed,
            solo_founder_override_acknowledged=payload.solo_founder_override_acknowledged,
        )
    except Exception as exc:
        _raise_service_error(exc)
