from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class BillingConfigResponse(BaseModel):
    publishable_key: str
    max_cards: int = Field(default=3, ge=1, le=10)
    portal_return_url: str | None = None


class PaymentMethodSummaryResponse(BaseModel):
    id: str
    brand: str | None = None
    last4: str | None = None
    exp_month: int | None = None
    exp_year: int | None = None
    funding: str | None = None
    is_default: bool = False
    created_at: str | None = None


class SubscriptionSummaryResponse(BaseModel):
    id: str
    status: str
    collection_method: str | None = None
    cancel_at_period_end: bool = False
    current_period_end: str | None = None
    default_payment_method_id: str | None = None
    product_names: list[str] = Field(default_factory=list)


class BillingOverviewResponse(BaseModel):
    customer_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    chain_label: str | None = None
    max_cards: int = Field(default=3, ge=1, le=10)
    cards_on_file: int = 0
    can_add_card: bool = True
    default_payment_method_id: str | None = None
    payment_methods: list[PaymentMethodSummaryResponse] = Field(default_factory=list)
    subscriptions: list[SubscriptionSummaryResponse] = Field(default_factory=list)


class SetupIntentResponse(BaseModel):
    client_secret: str
    customer_id: str
    max_cards: int = Field(default=3, ge=1, le=10)


class BillingPortalSessionResponse(BaseModel):
    url: str


class PaymentMethodActionResponse(BaseModel):
    success: bool = True
    message: str
    payment_method_id: str | None = None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def build_payment_method_summary(
    item: dict[str, Any],
    *,
    default_payment_method_id: str | None = None,
) -> PaymentMethodSummaryResponse:
    card = item.get("card") or {}
    item_id = _normalize_text(item.get("id"))
    return PaymentMethodSummaryResponse(
        id=item_id,
        brand=_normalize_text(card.get("brand")) or None,
        last4=_normalize_text(card.get("last4")) or None,
        exp_month=card.get("exp_month"),
        exp_year=card.get("exp_year"),
        funding=_normalize_text(card.get("funding")) or None,
        is_default=bool(item_id and item_id == _normalize_text(default_payment_method_id)),
        created_at=_normalize_text(item.get("created")) or None,
    )


def build_subscription_summary(item: dict[str, Any]) -> SubscriptionSummaryResponse:
    product_names: list[str] = []
    items = (((item.get("items") or {}).get("data")) or []) if isinstance(item, dict) else []
    for entry in items:
        price = (entry or {}).get("price") or {}
        product = price.get("product") or {}
        name = _normalize_text(product.get("name"))
        if name:
            product_names.append(name)

    default_payment_method = item.get("default_payment_method")
    if isinstance(default_payment_method, dict):
        default_payment_method_id = _normalize_text(default_payment_method.get("id")) or None
    else:
        default_payment_method_id = _normalize_text(default_payment_method) or None

    return SubscriptionSummaryResponse(
        id=_normalize_text(item.get("id")),
        status=_normalize_text(item.get("status")) or "unknown",
        collection_method=_normalize_text(item.get("collection_method")) or None,
        cancel_at_period_end=bool(item.get("cancel_at_period_end")),
        current_period_end=_to_datetime_string(item.get("current_period_end")),
        default_payment_method_id=default_payment_method_id,
        product_names=product_names,
    )


def _to_datetime_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), UTC).isoformat()
    except Exception:
        normalized = _normalize_text(value)
        return normalized or None
