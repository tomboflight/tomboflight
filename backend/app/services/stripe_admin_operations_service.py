"""Protected Stripe operations for the Master Admin console.

All card entry happens on Stripe-hosted surfaces (Checkout, Payment Links,
Hosted Invoice Page, Billing Portal). No raw card numbers or CVC values ever
pass through or are stored in Tomb of Light. Only safe Stripe references
(customer, session, invoice, subscription, payment intent, price IDs) and
safe card metadata (brand, last4) are handled.
"""

from __future__ import annotations

import logging
import hashlib
from typing import Any, Optional, cast
from urllib.parse import urlencode, urlparse

import stripe
from pymongo.database import Database

from app.config import settings
from app.database import get_database
from app.core.package_catalog import get_addon, normalize_addon_code
from app.services.audit_log_service import write_audit_log
from app.services.billing_service import (
    _ensure_stripe_customer_for_user,
    _require_stripe_secret_key,
    _stripe_to_dict,
)
from app.services.paid_addon_service import validate_paid_addon_purchase_target
from app.services.nft_addon_service import NFT_ADDON_CODES

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


def _idempotency_options(idempotency_key: str, suffix: str) -> dict[str, str]:
    normalized = _normalize(idempotency_key)
    if not normalized:
        return {}
    return {"idempotency_key": f"{normalized}:{suffix}"[:255]}


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


def ensure_customer(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    user = _find_customer_user(customer_email)
    customer = _ensure_stripe_customer_for_user(
        user,
        idempotency_key=f"{_normalize(idempotency_key)}:customer" if _normalize(idempotency_key) else "",
    )
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
    idempotency_key: str = "",
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
            **_idempotency_options(idempotency_key, "payment_link"),
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


def create_paid_addon_checkout(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    project_id: str,
    addon_code: str,
    price_id: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Create a project-bound Stripe Checkout session for a service add-on."""

    reason = _require_reason(reason)
    code = normalize_addon_code(addon_code)
    addon = get_addon(code)
    if not addon:
        raise ValueError("A known Tomb of Light add-on code is required.")
    if code in NFT_ADDON_CODES:
        raise ValueError("NFT add-ons must use the customer mint-credit checkout workflow.")
    price_id = _normalize(price_id)
    if not price_id.startswith("price_"):
        raise ValueError("A valid Stripe price id (price_...) is required.")
    user = _find_customer_user(customer_email)
    project = validate_paid_addon_purchase_target(user=user, project_id=project_id, addon_code=code)
    normalized_project_id = _normalize(project.get("_id") or project_id)
    expected_cents = int(round(float(addon.get("price_usd") or 0) * 100))
    if expected_cents <= 0:
        raise ValueError("This add-on requires a custom quote and cannot use fixed-price checkout.")

    _require_stripe_secret_key()
    price = _stripe_to_dict(stripe.Price.retrieve(price_id, expand=["product"]))
    product = price.get("product") or {}
    if not isinstance(product, dict):
        raise ValueError("Stripe price product metadata is unavailable.")
    product_code = normalize_addon_code((product.get("metadata") or {}).get("addon_code"))
    product_name = _normalize(product.get("name"))
    if product_code != code or product_name != _normalize(addon.get("display_name")):
        raise ValueError("Stripe product metadata does not match the selected Tomb of Light add-on.")
    if _normalize(price.get("currency")).lower() != "usd" or int(price.get("unit_amount") or 0) != expected_cents:
        raise ValueError("Stripe price does not match the approved add-on catalog price.")

    customer = _ensure_stripe_customer_for_user(
        user,
        idempotency_key=f"{_normalize(idempotency_key)}:customer" if _normalize(idempotency_key) else "",
    )
    customer_id = _normalize(customer.get("id"))
    user_id = _normalize(user.get("_id") or user.get("id") or user.get("user_id"))
    recurring = bool(price.get("recurring"))
    billing_interval = _normalize((price.get("recurring") or {}).get("interval")) if recurring else "one_time"
    reference = "tol:" + urlencode(
        {
            "v": "1",
            "u": user_id,
            "p": normalized_project_id,
            "k": code,
            "t": "addon",
            "b": billing_interval or "one_time",
        }
    )
    metadata = {
        "item_type": "addon",
        "addon_code": code,
        "project_id": normalized_project_id,
        "user_id": user_id,
        "created_by_admin_control": "true",
    }
    raw_app_base = _normalize(settings.nft_default_external_url).rstrip("/") or "https://tomboflight.com"
    parsed_app_base = urlparse(raw_app_base)
    if parsed_app_base.scheme not in {"http", "https"} or not parsed_app_base.netloc:
        raise RuntimeError("The public Tomb of Light URL is not configured for Stripe Checkout.")
    app_base = f"{parsed_app_base.scheme}://{parsed_app_base.netloc}"
    session_parameters: dict[str, Any] = {
        "mode": "subscription" if recurring else "payment",
        "customer": customer_id,
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": reference,
        "metadata": metadata,
        "success_url": f"{app_base}/thank-you.html?session_id={{CHECKOUT_SESSION_ID}}&type=addon&package={code}",
        "cancel_url": f"{app_base}/dashboard.html#billing",
        "allow_promotion_codes": False,
        **_idempotency_options(
            idempotency_key
            or hashlib.sha256(f"{user_id}:{normalized_project_id}:{code}".encode("utf-8")).hexdigest(),
            "addon_checkout",
        ),
    }
    if recurring:
        session_parameters["subscription_data"] = {"metadata": metadata}
    else:
        session_parameters["payment_intent_data"] = {"metadata": metadata}
    session = _stripe_to_dict(stripe.checkout.Session.create(**session_parameters))
    checkout_url = _normalize(session.get("url"))
    parsed_checkout = urlparse(checkout_url)
    if parsed_checkout.scheme != "https" or parsed_checkout.netloc != "checkout.stripe.com":
        raise RuntimeError("Stripe did not return a valid hosted Checkout URL.")
    _audit(
        admin_user,
        action="create_paid_addon_checkout",
        target_id=_normalize(session.get("id")) or normalized_project_id,
        reason=reason,
        details={"project_id": normalized_project_id, "addon_code": code, "price_id": price_id},
    )
    return {
        "session_id": _normalize(session.get("id")),
        "checkout_url": checkout_url,
        "customer_id": customer_id,
        "project_id": normalized_project_id,
        "addon_code": code,
        "amount_cents": expected_cents,
        "currency": "usd",
        "payment_activation": "stripe_webhook_then_manual_fulfillment",
        "expires_at": session.get("expires_at"),
    }


def create_and_send_invoice(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    amount_cents: int,
    description: str,
    days_until_due: int = 7,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    if int(amount_cents) <= 0:
        raise ValueError("amount_cents must be a positive integer.")
    description = _normalize(description)
    if not description:
        raise ValueError("An invoice line description is required.")
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(
        user,
        idempotency_key=f"{_normalize(idempotency_key)}:customer" if _normalize(idempotency_key) else "",
    )
    customer_id = _normalize(customer.get("id"))
    invoice = _stripe_to_dict(
        stripe.Invoice.create(
            customer=customer_id,
            collection_method="send_invoice",
            days_until_due=max(1, int(days_until_due)),
            auto_advance=False,
            **_idempotency_options(idempotency_key, "invoice"),
        )
    )
    stripe.InvoiceItem.create(
        customer=customer_id,
        amount=int(amount_cents),
        currency="usd",
        description=description,
        invoice=invoice["id"],
        **_idempotency_options(idempotency_key, "invoice_item"),
    )
    finalized = _stripe_to_dict(
        stripe.Invoice.finalize_invoice(
            invoice["id"],
            **_idempotency_options(idempotency_key, "invoice_finalize"),
        )
    )
    sent = _stripe_to_dict(
        stripe.Invoice.send_invoice(
            finalized["id"],
            **_idempotency_options(idempotency_key, "invoice_send"),
        )
    )
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
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    price_id = _normalize(price_id)
    if not price_id.startswith("price_"):
        raise ValueError("A valid Stripe price id (price_...) is required.")
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(
        user,
        idempotency_key=f"{_normalize(idempotency_key)}:customer" if _normalize(idempotency_key) else "",
    )
    customer_id = _normalize(customer.get("id"))
    subscription = _stripe_to_dict(
        stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            collection_method="send_invoice",
            days_until_due=7,
            **_idempotency_options(idempotency_key, "subscription_create"),
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
    idempotency_key: str = "",
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
            **_idempotency_options(idempotency_key, "subscription_change"),
        )
    )
    _audit(admin_user, action="change_subscription_price", target_id=subscription["id"], reason=reason,
           details={"new_price_id": price_id})
    return {"subscription_id": subscription["id"], "status": _normalize(updated.get("status")), "price_id": price_id}


def pause_subscription(
    admin_user: dict[str, Any],
    *,
    subscription_id: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    subscription = _retrieve_subscription(subscription_id)
    updated = _stripe_to_dict(
        stripe.Subscription.modify(
            subscription["id"],
            pause_collection={"behavior": "keep_as_draft"},
            **_idempotency_options(idempotency_key, "subscription_pause"),
        )
    )
    _audit(admin_user, action="pause_subscription", target_id=subscription["id"], reason=reason)
    return {"subscription_id": subscription["id"], "paused": True, "status": _normalize(updated.get("status"))}


def resume_subscription(
    admin_user: dict[str, Any],
    *,
    subscription_id: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    subscription = _retrieve_subscription(subscription_id)
    updated = _stripe_to_dict(
        stripe.Subscription.modify(
            subscription["id"],
            pause_collection="",
            **_idempotency_options(idempotency_key, "subscription_resume"),
        )
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
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    subscription = _retrieve_subscription(subscription_id)
    if at_period_end:
        updated = _stripe_to_dict(
            stripe.Subscription.modify(
                subscription["id"],
                cancel_at_period_end=True,
                **_idempotency_options(idempotency_key, "subscription_cancel_period_end"),
            )
        )
    else:
        if not confirm:
            raise ValueError("Immediate cancellation requires explicit confirmation.")
        updated = _stripe_to_dict(
            stripe.Subscription.cancel(
                subscription["id"],
                **_idempotency_options(idempotency_key, "subscription_cancel_now"),
            )
        )
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
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(
        user,
        idempotency_key=f"{_normalize(idempotency_key)}:customer" if _normalize(idempotency_key) else "",
    )
    customer_id = _normalize(customer.get("id"))
    session = _stripe_to_dict(
        stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=settings.stripe_billing_portal_return_url_clean
            or "https://tomboflight.com/billing.html",
            **_idempotency_options(idempotency_key, "payment_method_portal"),
        )
    )
    _audit(admin_user, action="send_payment_method_update_link", target_id=customer_id, reason=reason)
    return {"customer_id": customer_id, "portal_url": _normalize(session.get("url"))}


def retry_invoice_payment(
    admin_user: dict[str, Any],
    *,
    invoice_id: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    reason = _require_reason(reason)
    invoice_id = _normalize(invoice_id)
    if not invoice_id.startswith("in_"):
        raise ValueError("A valid Stripe invoice id (in_...) is required.")
    _require_stripe_secret_key()
    invoice = _stripe_to_dict(stripe.Invoice.retrieve(invoice_id))
    if _normalize(invoice.get("status")) not in {"open", "uncollectible"}:
        raise ValueError(f"Invoice status '{invoice.get('status')}' is not retryable.")
    paid = _stripe_to_dict(
        stripe.Invoice.pay(
            invoice_id,
            **_idempotency_options(idempotency_key, "invoice_retry"),
        )
    )
    _audit(admin_user, action="retry_invoice_payment", target_id=invoice_id, reason=reason)
    return {"invoice_id": invoice_id, "status": _normalize(paid.get("status")), "paid": bool(paid.get("paid"))}


def refund_payment(
    admin_user: dict[str, Any],
    *,
    payment_intent_id: str,
    amount_cents: int = 0,
    refund_reason: str = "requested_by_customer",
    confirm: bool = False,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Issue a Stripe refund after the governed local preflight has passed."""

    reason = _require_reason(reason)
    payment_intent_id = _normalize(payment_intent_id)
    if not payment_intent_id.startswith("pi_"):
        raise ValueError("A valid Stripe payment intent id (pi_...) is required.")
    if not confirm:
        raise ValueError("Refund execution requires explicit confirmation.")
    if int(amount_cents) < 0:
        raise ValueError("Refund amount cannot be negative.")
    normalized_refund_reason = _normalize(refund_reason).lower() or "requested_by_customer"
    if normalized_refund_reason not in {"duplicate", "fraudulent", "requested_by_customer"}:
        raise ValueError("Stripe refund reason must be duplicate, fraudulent, or requested_by_customer.")

    _require_stripe_secret_key()
    payment_intent = _stripe_to_dict(stripe.PaymentIntent.retrieve(payment_intent_id))
    refundable_amount = int(payment_intent.get("amount_received") or payment_intent.get("amount") or 0)
    requested_amount = int(amount_cents or 0)
    if requested_amount and refundable_amount and requested_amount > refundable_amount:
        raise ValueError("Refund amount exceeds the Stripe payment amount.")
    parameters: dict[str, Any] = {
        "payment_intent": payment_intent_id,
        "reason": normalized_refund_reason,
        "metadata": {
            "tol_admin_reason": reason[:500],
            "tol_actor_email": _normalize(admin_user.get("email")).lower()[:200],
        },
    }
    if requested_amount:
        parameters["amount"] = requested_amount
    refund = _stripe_to_dict(
        stripe.Refund.create(
            **parameters,
            **_idempotency_options(idempotency_key, "refund"),
        )
    )
    refund_id = _normalize(refund.get("id"))
    _audit(
        admin_user,
        action="refund_payment",
        target_id=refund_id or payment_intent_id,
        reason=reason,
        details={
            "payment_intent_id": payment_intent_id,
            "amount": refund.get("amount"),
            "status": _normalize(refund.get("status")),
            "stripe_reason": normalized_refund_reason,
        },
    )
    return {
        "refund_id": refund_id,
        "payment_intent_id": payment_intent_id,
        "amount": int(refund.get("amount") or requested_amount or refundable_amount),
        "currency": _normalize(refund.get("currency") or payment_intent.get("currency")) or "usd",
        "status": _normalize(refund.get("status")) or "pending",
        "reason": normalized_refund_reason,
    }


def create_customer_credit(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    amount_cents: int,
    description: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Create a non-cash credit on the customer's Stripe balance."""

    reason = _require_reason(reason)
    amount_cents = int(amount_cents)
    if amount_cents <= 0:
        raise ValueError("Credit amount must be positive.")
    description = _normalize(description) or reason
    user = _find_customer_user(customer_email)
    _require_stripe_secret_key()
    customer = _ensure_stripe_customer_for_user(
        user,
        idempotency_key=f"{_normalize(idempotency_key)}:customer" if _normalize(idempotency_key) else "",
    )
    customer_id = _normalize(customer.get("id"))
    transaction = _stripe_to_dict(
        stripe.Customer.create_balance_transaction(
            customer_id,
            amount=-amount_cents,
            currency="usd",
            description=description,
            metadata={"tol_admin_reason": reason[:500]},
            **_idempotency_options(idempotency_key, "customer_credit"),
        )
    )
    transaction_id = _normalize(transaction.get("id"))
    _audit(
        admin_user,
        action="create_customer_credit",
        target_id=transaction_id or customer_id,
        reason=reason,
        details={"customer_id": customer_id, "amount_cents": amount_cents},
    )
    return {
        "balance_transaction_id": transaction_id,
        "customer_id": customer_id,
        "amount": amount_cents,
        "currency": "usd",
        "type": "customer_balance_credit",
    }


def apply_subscription_discount(
    admin_user: dict[str, Any],
    *,
    customer_email: str,
    subscription_id: str,
    coupon_id: str,
    reason: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Apply an existing approved Stripe coupon to a customer subscription."""

    reason = _require_reason(reason)
    coupon_id = _normalize(coupon_id)
    if not coupon_id:
        raise ValueError("A Stripe coupon id is required.")
    user = _find_customer_user(customer_email)
    subscription = _retrieve_subscription(subscription_id)
    expected_customer_id = _normalize(user.get("stripe_customer_id"))
    subscription_customer_id = _normalize(subscription.get("customer"))
    if expected_customer_id and subscription_customer_id != expected_customer_id:
        raise ValueError("The Stripe subscription does not belong to the selected customer.")
    _require_stripe_secret_key()
    stripe.Coupon.retrieve(coupon_id)
    updated = _stripe_to_dict(
        stripe.Subscription.modify(
            subscription["id"],
            discounts=[{"coupon": coupon_id}],
            **_idempotency_options(idempotency_key, "subscription_discount"),
        )
    )
    _audit(
        admin_user,
        action="apply_subscription_discount",
        target_id=subscription["id"],
        reason=reason,
        details={"coupon_id": coupon_id, "customer_id": subscription_customer_id},
    )
    return {
        "subscription_id": subscription["id"],
        "customer_id": subscription_customer_id,
        "coupon_id": coupon_id,
        "status": _normalize(updated.get("status")),
    }


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
