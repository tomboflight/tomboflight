from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.schemas.billing import (
    BillingConfigResponse,
    BillingOverviewResponse,
    BillingPortalSessionResponse,
    PaymentMethodActionResponse,
    SetupIntentResponse,
    build_payment_method_summary,
    build_subscription_summary,
)
from app.services.billing_service import (
    create_billing_portal_session_for_user,
    create_setup_intent_for_user,
    detach_payment_method_for_user,
    get_billing_config,
    get_billing_overview,
    set_default_payment_method_for_user,
)

router = APIRouter(prefix="/billing", tags=["Billing"])


class BillingPortalRequest(BaseModel):
    return_url: str | None = Field(default=None, max_length=500)


@router.get("/config", response_model=BillingConfigResponse)
def billing_config_route(current_user: dict[str, Any] = Depends(get_current_user)):
    del current_user
    return get_billing_config()


@router.get("/overview", response_model=BillingOverviewResponse)
def billing_overview_route(current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        payload = get_billing_overview(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return BillingOverviewResponse(
        customer_id=payload.get("customer_id"),
        error_code=payload.get("error_code"),
        message=payload.get("message"),
        max_cards=int(payload.get("max_cards") or 3),
        cards_on_file=int(payload.get("cards_on_file") or 0),
        can_add_card=bool(payload.get("can_add_card")),
        default_payment_method_id=payload.get("default_payment_method_id"),
        payment_methods=[
            build_payment_method_summary(
                item,
                default_payment_method_id=payload.get("default_payment_method_id"),
            )
            for item in payload.get("payment_methods") or []
        ],
        subscriptions=[
            build_subscription_summary(item)
            for item in payload.get("subscriptions") or []
        ],
    )


@router.post("/setup-intent", response_model=SetupIntentResponse)
def create_setup_intent_route(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return create_setup_intent_for_user(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/payment-methods/{payment_method_id}/default",
    response_model=PaymentMethodActionResponse,
)
def set_default_payment_method_route(
    payment_method_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return set_default_payment_method_for_user(current_user, payment_method_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete(
    "/payment-methods/{payment_method_id}",
    response_model=PaymentMethodActionResponse,
)
def detach_payment_method_route(
    payment_method_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return detach_payment_method_for_user(current_user, payment_method_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/portal-session", response_model=BillingPortalSessionResponse)
def create_billing_portal_session_route(
    payload: BillingPortalRequest | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return create_billing_portal_session_for_user(
            current_user,
            return_url=payload.return_url if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
