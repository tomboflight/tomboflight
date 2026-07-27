"""Protected Stripe operations routes for the Master Admin console.

Card entry always happens on Stripe-hosted surfaces. These routes never
accept or return raw card numbers or CVC values.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies.auth import require_permission
from app.services import stripe_admin_operations_service as stripe_ops

router = APIRouter(prefix="/admin/stripe-ops", tags=["Admin Stripe Operations"])

_BILLING_PERMISSION = "admin.control.billing"


def _run(fn, /, **kwargs) -> Any:
    try:
        return fn(**kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


class CustomerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str = Field(..., min_length=3)
    reason: str = Field(..., min_length=3)


class PaymentLinkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_id: str = Field(..., min_length=6)
    quantity: int = Field(default=1, ge=1, le=10)
    reason: str = Field(..., min_length=3)


class InvoicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str = Field(..., min_length=3)
    amount_cents: int = Field(..., gt=0)
    description: str = Field(..., min_length=3)
    days_until_due: int = Field(default=7, ge=1, le=90)
    reason: str = Field(..., min_length=3)


class SubscriptionCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str = Field(..., min_length=3)
    price_id: str = Field(..., min_length=6)
    reason: str = Field(..., min_length=3)


class SubscriptionChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription_id: str = Field(..., min_length=4)
    price_id: str = Field(..., min_length=6)
    reason: str = Field(..., min_length=3)


class SubscriptionActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription_id: str = Field(..., min_length=4)
    reason: str = Field(..., min_length=3)


class SubscriptionCancelPayload(SubscriptionActionPayload):
    at_period_end: bool = True
    confirm: bool = False


class InvoiceRetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: str = Field(..., min_length=4)
    reason: str = Field(..., min_length=3)


@router.post("/customers/ensure")
def ensure_customer(
    payload: CustomerPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.ensure_customer,
        admin_user=current_user,
        customer_email=payload.customer_email,
        reason=payload.reason,
    )


@router.get("/customers/open")
def open_customer(
    customer_email: str = Query(..., min_length=3),
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.open_customer_in_stripe,
        admin_user=current_user,
        customer_email=customer_email,
    )


@router.post("/payment-links")
def create_payment_link(
    payload: PaymentLinkPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.create_payment_link,
        admin_user=current_user,
        price_id=payload.price_id,
        quantity=payload.quantity,
        reason=payload.reason,
    )


@router.post("/invoices")
def create_and_send_invoice(
    payload: InvoicePayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.create_and_send_invoice,
        admin_user=current_user,
        customer_email=payload.customer_email,
        amount_cents=payload.amount_cents,
        description=payload.description,
        days_until_due=payload.days_until_due,
        reason=payload.reason,
    )


@router.post("/invoices/retry")
def retry_invoice(
    payload: InvoiceRetryPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.retry_invoice_payment,
        admin_user=current_user,
        invoice_id=payload.invoice_id,
        reason=payload.reason,
    )


@router.post("/subscriptions")
def create_subscription(
    payload: SubscriptionCreatePayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.create_subscription,
        admin_user=current_user,
        customer_email=payload.customer_email,
        price_id=payload.price_id,
        reason=payload.reason,
    )


@router.post("/subscriptions/change-price")
def change_subscription_price(
    payload: SubscriptionChangePayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.change_subscription_price,
        admin_user=current_user,
        subscription_id=payload.subscription_id,
        price_id=payload.price_id,
        reason=payload.reason,
    )


@router.post("/subscriptions/pause")
def pause_subscription(
    payload: SubscriptionActionPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.pause_subscription,
        admin_user=current_user,
        subscription_id=payload.subscription_id,
        reason=payload.reason,
    )


@router.post("/subscriptions/resume")
def resume_subscription(
    payload: SubscriptionActionPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.resume_subscription,
        admin_user=current_user,
        subscription_id=payload.subscription_id,
        reason=payload.reason,
    )


@router.post("/subscriptions/cancel")
def cancel_subscription(
    payload: SubscriptionCancelPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.cancel_subscription,
        admin_user=current_user,
        subscription_id=payload.subscription_id,
        at_period_end=payload.at_period_end,
        confirm=payload.confirm,
        reason=payload.reason,
    )


@router.post("/payment-method-update-link")
def send_payment_method_update_link(
    payload: CustomerPayload,
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.send_payment_method_update_link,
        admin_user=current_user,
        customer_email=payload.customer_email,
        reason=payload.reason,
    )


@router.get("/customers/history")
def customer_history(
    customer_email: str = Query(..., min_length=3),
    current_user: dict[str, Any] = Depends(require_permission(_BILLING_PERMISSION)),
):
    return _run(
        stripe_ops.customer_payment_history,
        admin_user=current_user,
        customer_email=customer_email,
    )
