"""Protected Stripe operations for the Master Admin console.

All card entry happens on Stripe-hosted surfaces (Checkout, Payment Links,
Hosted Invoice Page, Billing Portal). No raw card numbers or CVC values ever
pass through or are stored in Tomb of Light. Only safe Stripe references
(customer, session, invoice, subscription, payment intent, price IDs) and
safe card metadata (brand, last4) are handled.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

import stripe
from pymongo.database import Database

from app.config import settings
from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services.billing_service import (
    _ensure_stripe_customer_for_user,
    _require_stripe_secret_key,
    _stripe_to_dict,
)

logger = logging.getLogger(__name__)

STRIPE_DASHBOARD_BASE = "https://dashboard.stripe.com"


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _db() -> Database:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    return cast(Database, db)


def _require_reason(reason: str) -> str:
    normalized = _normalize(reason)
    if len(normalized) < 3:
        raise ValueError("A reason is required for Stripe operations.")
    return normalized


def _find_customer_user(customer_email: str) -> dict[str, Any]:
    email = _normalize(customer_email).lower()
    if not email:
        raise ValueError("customer_email is required.")
    user = _db()["users"].find_one({"email": email})
    if not user:
        raise ValueError("No Tomb of Light account exists for that email.")
    return user


def _audit(
    admin_user: dict[str, Any],
    *,
    action: str,
    target_id: str,
    reason: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    write_audit_log(
        actor_user_id=_normalize(admin_user.get("_id") or admin_user.get("id")) or None,
        actor_email=_normalize(admin_user.get("email")).lower() or None,
        actor_name=_normalize(admin_user.get("full_name") or admin_user.get("name")) or None,
        action=f"stripe_ops.{action}",
        target_type="stripe",
        target_id=target_id,
        context={"reason": reason, "surface": "master_admin_stripe_operations"},
        details=details or {},
    )


def _safe_card_metadata(payment_method: dict[str, Any]) -> dict[str, Any]:
    card = payment_method.get("card") or {}
    return {
        "id": _normalize(payment_method.get("id")),
        "brand": _normalize(card.get("brand")),
        "last4": _normalize(card.get("last4")),
        "exp_month": card.get("exp_month"),
        "exp_year": card.get("exp_year"),
    }


def ensure_customer(admin_user: dict[str, Any], *, customer_email: str, reason: str) -> dict[str, Any]:
    reason = _require_reason(reason)
    user = _find_customer_user(customer_email)
    customer = _ensure_stripe_customer_for_user(user)
    customer_id = _normalize(customer.get("id"))
    _audit(admin_user, action="ensure_customer", target_id=customer_id, reason=reason,
           details={"customer_email": _normalize(customer_email).lower()})
    return {
        "customer_id": customer_id,
        "email": _normalize(customer.get("email")) or _normalize(customer_email).lower(),
        "dashboard_url": f"{STRIPE_DASHBOARD_BASE}/customers/{customer_id}",
    }


def open_customer_in_stripe(admin_user: dict[str, Any], *, customer_email: str) -> dict[str, Any]:
    user = _find_customer_user(customer_email)
    customer_id = _normalize(user.get("stripe_customer_id"))
    if not customer_id:
        raise ValueError("Customer has no Stripe customer record yet. Create one first.")
    return {
        "customer_id": customer_id,
        "dashboard_url": f"{STRIPE_DASHBOARD_BASE}/customers/{customer_id}",
    }


def create_payment_link(
    admin_user: dict[str, Any],
    *,
    price_id: str,
    quantity: int = 1,
    reason: str,
) -> dict[str, Any]:
    reason = _require_reason(reason)
    price_id = _normalize(price_id)
    if not price_id.startswith("price_"):
        raise ValueError("A valid Stripe price id (price_...) is required.")
    _require_stripe_secret_key()
    price = _stripe_to_dict(stripe.Price.retrieve(price_id))
    link = _stripe_to_dict(
        stripe.PaymentLink.create(
            line_items=[{"price": price_id, "quantity": max(1, int(quantity))}],
        )
    )
    link_id = _normalize(link.get("id"))
    mode = "subscription" if _normalize(price.get("type")) == "recurring" else "one_time"
    _audit(admin_user, action="create_payment_link", target_id=link_id, reason=reason,
           details={"price_id": price_id, "mode": mode})
    return {
        "payment_link_id": link_id,
        "url": _normalize(link.get("url")),
        "mode": mode,
        "price_id": price_id,
    }


def create_and_send_invoice(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    amount_cents: int,
    description: str,
    days_until_due: int = 7,
    reason: str,
) -> dict[str, Any]:
    reason = _require_reason(reason)
    if int(amount_cents) <= 0:
        raise ValueError("amount_cents must be a positive integer.")
    description = _normalize(description)
    if not description:
        raise ValueError("An invoice line description is required.")
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(user)
    customer_id = _normalize(customer.get("id"))
    invoice = _stripe_to_dict(
        stripe.Invoice.create(
            customer=customer_id,
            collection_method="send_invoice",
            days_until_due=max(1, int(days_until_due)),
            auto_advance=False,
        )
    )
    stripe.InvoiceItem.create(
        customer=customer_id,
        amount=int(amount_cents),
        currency="usd",
        description=description,
        invoice=invoice["id"],
    )
    finalized = _stripe_to_dict(stripe.Invoice.finalize_invoice(invoice["id"]))
    sent = _stripe_to_dict(stripe.Invoice.send_invoice(finalized["id"]))
    _audit(admin_user, action="create_and_send_invoice", target_id=_normalize(sent.get("id")), reason=reason,
           details={"customer_id": customer_id, "amount_cents": int(amount_cents)})
    return {
        "invoice_id": _normalize(sent.get("id")),
        "status": _normalize(sent.get("status")),
        "hosted_invoice_url": _normalize(sent.get("hosted_invoice_url")) or None,
        "customer_id": customer_id,
    }


def create_subscription(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    price_id: str,
    reason: str,
) -> dict[str, Any]:
    reason = _require_reason(reason)
    price_id = _normalize(price_id)
    if not price_id.startswith("price_"):
        raise ValueError("A valid Stripe price id (price_...) is required.")
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(user)
    customer_id = _normalize(customer.get("id"))
    subscription = _stripe_to_dict(
        stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            collection_method="send_invoice",
            days_until_due=7,
        )
    )
    _audit(admin_user, action="create_subscription", target_id=_normalize(subscription.get("id")), reason=reason,
           details={"customer_id": customer_id, "price_id": price_id})
    return {
        "subscription_id": _normalize(subscription.get("id")),
        "status": _normalize(subscription.get("status")),
        "customer_id": customer_id,
    }


def _retrieve_subscription(subscription_id: str) -> dict[str, Any]:
    subscription_id = _normalize(subscription_id)
    if not subscription_id.startswith("sub_"):
        raise ValueError("A valid Stripe subscription id (sub_...) is required.")
    _require_stripe_secret_key()
    return _stripe_to_dict(stripe.Subscription.retrieve(subscription_id))


def change_subscription_price(
    admin_user: dict[str, Any],
    *,
    subscription_id: str,
    price_id: str,
    reason: str,
) -> dict[str, Any]:
    reason = _require_reason(reason)
    price_id = _normalize(price_id)
    if not price_id.startswith("price_"):
        raise ValueError("A valid Stripe price id (price_...) is required.")
    subscription = _retrieve_subscription(subscription_id)
    items = ((subscription.get("items") or {}).get("data")) or []
    if not items:
        raise ValueError("Subscription has no line items to change.")
    updated = _stripe_to_dict(
        stripe.Subscription.modify(
            subscription["id"],
            items=[{"id": items[0]["id"], "price": price_id}],
            proration_behavior="create_prorations",
        )
    )
    _audit(admin_user, action="change_subscription_price", target_id=subscription["id"], reason=reason,
           details={"new_price_id": price_id})
    return {"subscription_id": subscription["id"], "status": _normalize(updated.get("status")), "price_id": price_id}


def pause_subscription(admin_user: dict[str, Any], *, subscription_id: str, reason: str) -> dict[str, Any]:
    reason = _require_reason(reason)
    subscription = _retrieve_subscription(subscription_id)
    updated = _stripe_to_dict(
        stripe.Subscription.modify(
            subscription["id"],
            pause_collection={"behavior": "keep_as_draft"},
        )
    )
    _audit(admin_user, action="pause_subscription", target_id=subscription["id"], reason=reason)
    return {"subscription_id": subscription["id"], "paused": True, "status": _normalize(updated.get("status"))}


def resume_subscription(admin_user: dict[str, Any], *, subscription_id: str, reason: str) -> dict[str, Any]:
    reason = _require_reason(reason)
    subscription = _retrieve_subscription(subscription_id)
    updated = _stripe_to_dict(
        stripe.Subscription.modify(subscription["id"], pause_collection="")
    )
    _audit(admin_user, action="resume_subscription", target_id=subscription["id"], reason=reason)
    return {"subscription_id": subscription["id"], "paused": False, "status": _normalize(updated.get("status"))}


def cancel_subscription(
    admin_user: dict[str, Any],
    *,
    subscription_id: str,
    at_period_end: bool = True,
    confirm: bool = False,
    reason: str,
) -> dict[str, Any]:
    reason = _require_reason(reason)
    subscription = _retrieve_subscription(subscription_id)
    if at_period_end:
        updated = _stripe_to_dict(
            stripe.Subscription.modify(subscription["id"], cancel_at_period_end=True)
        )
    else:
        if not confirm:
            raise ValueError("Immediate cancellation requires explicit confirmation.")
        updated = _stripe_to_dict(stripe.Subscription.cancel(subscription["id"]))
    _audit(admin_user, action="cancel_subscription", target_id=subscription["id"], reason=reason,
           details={"at_period_end": bool(at_period_end)})
    return {
        "subscription_id": subscription["id"],
        "status": _normalize(updated.get("status")),
        "cancel_at_period_end": bool(updated.get("cancel_at_period_end")),
    }


def send_payment_method_update_link(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    reason: str,
) -> dict[str, Any]:
    reason = _require_reason(reason)
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(user)
    customer_id = _normalize(customer.get("id"))
    session = _stripe_to_dict(
        stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=settings.stripe_billing_portal_return_url_clean
            or "https://tomboflight.com/billing.html",
        )
    )
    _audit(admin_user, action="send_payment_method_update_link", target_id=customer_id, reason=reason)
    return {"customer_id": customer_id, "portal_url": _normalize(session.get("url"))}


def retry_invoice_payment(admin_user: dict[str, Any], *, invoice_id: str, reason: str) -> dict[str, Any]:
    reason = _require_reason(reason)
    invoice_id = _normalize(invoice_id)
    if not invoice_id.startswith("in_"):
        raise ValueError("A valid Stripe invoice id (in_...) is required.")
    _require_stripe_secret_key()
    invoice = _stripe_to_dict(stripe.Invoice.retrieve(invoice_id))
    if _normalize(invoice.get("status")) not in {"open", "uncollectible"}:
        raise ValueError(f"Invoice status '{invoice.get('status')}' is not retryable.")
    paid = _stripe_to_dict(stripe.Invoice.pay(invoice_id))
    _audit(admin_user, action="retry_invoice_payment", target_id=invoice_id, reason=reason)
    return {"invoice_id": invoice_id, "status": _normalize(paid.get("status")), "paid": bool(paid.get("paid"))}


def customer_payment_history(admin_user: dict[str, Any], *, customer_email: str) -> dict[str, Any]:
    user = _find_customer_user(customer_email)
    customer_id = _normalize(user.get("stripe_customer_id"))
    if not customer_id:
        return {
            "customer_id": None,
            "payments": [],
            "invoices": [],
            "subscriptions": [],
            "failed_payments": [],
        }
    _require_stripe_secret_key()
    payments = _stripe_to_dict(stripe.PaymentIntent.list(customer=customer_id, limit=25))
    invoices = _stripe_to_dict(stripe.Invoice.list(customer=customer_id, limit=25))
    subscriptions = _stripe_to_dict(
        stripe.Subscription.list(customer=customer_id, status="all", limit=25)
    )

    def _payment(p: dict[str, Any]) -> dict[str, Any]:
        return {
            "payment_intent_id": _normalize(p.get("id")),
            "amount": p.get("amount"),
            "currency": _normalize(p.get("currency")),
            "status": _normalize(p.get("status")),
            "created": p.get("created"),
        }

    def _invoice(i: dict[str, Any]) -> dict[str, Any]:
        return {
            "invoice_id": _normalize(i.get("id")),
            "status": _normalize(i.get("status")),
            "amount_due": i.get("amount_due"),
            "amount_paid": i.get("amount_paid"),
            "currency": _normalize(i.get("currency")),
            "hosted_invoice_url": _normalize(i.get("hosted_invoice_url")) or None,
            "created": i.get("created"),
        }

    def _subscription(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "subscription_id": _normalize(s.get("id")),
            "status": _normalize(s.get("status")),
            "cancel_at_period_end": bool(s.get("cancel_at_period_end")),
            "paused": bool(s.get("pause_collection")),
            "created": s.get("created"),
        }

    payment_items = [_payment(p) for p in (payments.get("data") or [])]
    invoice_items = [_invoice(i) for i in (invoices.get("data") or [])]
    return {
        "customer_id": customer_id,
        "payments": payment_items,
        "invoices": invoice_items,
        "subscriptions": [_subscription(s) for s in (subscriptions.get("data") or [])],
        "failed_payments": [p for p in payment_items if p["status"] in {"requires_payment_method", "canceled"}]
        + [i for i in invoice_items if i["status"] == "open" and (i.get("amount_paid") or 0) == 0],
    }
