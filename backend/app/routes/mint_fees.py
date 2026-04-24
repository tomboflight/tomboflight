from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user, require_permission
from app.schemas.mint_fee import (
    MintFeeMarkPaidPayload,
    MintFeeQuotePayload,
    MintFeeRefreshNetworkQuotePayload,
    MintFeeWaivePayload,
)
from app.services.mint_fee_service import (
    get_project_mint_fee,
    get_project_mint_readiness,
    mark_mint_fee_paid,
    quote_mint_fee,
    refresh_network_quote,
    waive_mint_fee,
)

router = APIRouter(tags=["Mint Billing"])


def _http_400(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/projects/{project_id}/mint-fees")
def get_mint_fees(project_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    del current_user
    try:
        return get_project_mint_fee(project_id)
    except ValueError as exc:
        raise _http_400(exc) from exc


@router.post("/projects/{project_id}/mint-fees/quote")
def quote_project_mint_fees(
    project_id: str,
    payload: MintFeeQuotePayload,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    try:
        return quote_mint_fee(project_id, current_user, payload.model_dump())
    except ValueError as exc:
        raise _http_400(exc) from exc


@router.post("/projects/{project_id}/mint-fees/mark-paid")
def mark_project_mint_fees_paid(
    project_id: str,
    payload: MintFeeMarkPaidPayload,
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    try:
        return mark_mint_fee_paid(project_id, current_user, payload.mint_fee_notes)
    except ValueError as exc:
        raise _http_400(exc) from exc


@router.post("/admin/projects/{project_id}/mint-fees/waive")
def waive_project_mint_fees(
    project_id: str,
    payload: MintFeeWaivePayload,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.mint")),
):
    try:
        return waive_mint_fee(project_id, current_user, payload.mint_fee_notes)
    except ValueError as exc:
        raise _http_400(exc) from exc


@router.post("/admin/projects/{project_id}/mint-fees/refresh-network-quote")
def refresh_project_network_quote(
    project_id: str,
    payload: MintFeeRefreshNetworkQuotePayload,
    current_user: dict[str, Any] = Depends(require_permission("admin.control.mint")),
):
    try:
        return refresh_network_quote(project_id, current_user, payload.model_dump())
    except ValueError as exc:
        raise _http_400(exc) from exc


@router.get("/projects/{project_id}/mint-readiness")
def get_mint_readiness(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    del current_user
    try:
        return get_project_mint_readiness(project_id)
    except ValueError as exc:
        raise _http_400(exc) from exc
