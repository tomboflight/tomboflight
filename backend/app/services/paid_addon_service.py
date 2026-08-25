"""Payment-bound fulfillment for Tomb of Light catalog add-ons.

Catalog add-ons are commercial products.  They may be activated only from an
authoritative paid order created by the Stripe webhook path.  The service
controls surface may adjust operational limits, but it may not fabricate a
purchase or directly toggle a catalog add-on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from bson import ObjectId
from pymongo.database import Database

from app.core.package_catalog import get_addon, normalize_addon_code, normalize_package_code
from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services.entitlement_service import can_purchase_addon, resolve_project_entitlements
from app.services.nft_addon_service import NFT_ADDON_CODES
from app.services.order_service_constants import (
    AUTHORITATIVE_ORDER_SOURCES,
    FULFILLMENT_COMPLETE,
    PAID_ORDER_STATUSES,
)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _db() -> Database:
    database = cast(Database | None, get_database())
    if database is None:
        raise RuntimeError("Database is not connected.")
    return database


def _id_candidates(value: Any) -> list[Any]:
    normalized = _normalize(value)
    candidates: list[Any] = []
    if normalized:
        candidates.append(normalized)
    if ObjectId.is_valid(normalized):
        candidates.append(ObjectId(normalized))
    return list(dict.fromkeys(candidates))


def _project(project_id: str) -> dict[str, Any]:
    project = _db()["projects"].find_one({"_id": {"$in": _id_candidates(project_id)}})
    if not isinstance(project, dict):
        raise ValueError("Project not found.")
    return project


def _user_can_purchase_for_project(user: dict[str, Any], project: dict[str, Any]) -> bool:
    user_ids = _id_candidates(user.get("_id") or user.get("id") or user.get("user_id"))
    owner_ids = _id_candidates(project.get("owner_user_id"))
    if set(user_ids).intersection(owner_ids):
        return True

    user_email = _normalize_email(user.get("email"))
    owner_email = _normalize_email(project.get("owner_email"))
    if user_email and owner_email and user_email == owner_email:
        return True

    member = _db()["project_members"].find_one(
        {
            "project_id": {"$in": _id_candidates(project.get("_id"))},
            "user_id": {"$in": user_ids},
            "status": {"$in": ["active", "accepted"]},
            "role": {"$in": ["billing_owner", "co_owner"]},
        }
    )
    return isinstance(member, dict)


def validate_paid_addon_purchase_target(
    *,
    user: dict[str, Any],
    project_id: str,
    addon_code: str,
) -> dict[str, Any]:
    """Validate ownership and package compatibility before recording payment."""

    code = normalize_addon_code(addon_code)
    addon = get_addon(code)
    if not addon:
        raise ValueError("Checkout product is not a recognized Tomb of Light add-on.")
    if code in NFT_ADDON_CODES:
        raise ValueError("NFT add-ons must use the dedicated mint-credit validation path.")

    project = _project(project_id)
    if not _user_can_purchase_for_project(user, project):
        raise ValueError("Add-on checkout does not belong to this customer workspace.")
    package_code = normalize_package_code(
        project.get("package_code") or project.get("package_slug") or project.get("package_type")
    )
    if not package_code or not can_purchase_addon(package_code, code):
        raise ValueError("This add-on is not available for the project's current package and lane.")
    return project


def _order_addon_code(order: dict[str, Any]) -> str:
    return normalize_addon_code(
        order.get("addon_code") or order.get("purchase_code") or order.get("package_code")
    )


def _entitlement(project_id: Any) -> dict[str, Any]:
    document = _db()["project_entitlements"].find_one(
        {"project_id": {"$in": _id_candidates(project_id)}}
    )
    if not isinstance(document, dict):
        raise ValueError("The project entitlement must exist before activating a paid add-on.")
    return document


def activate_paid_addon_order(
    *,
    order: dict[str, Any],
    actor: dict[str, Any] | None,
    reason: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Activate one non-NFT catalog add-on from a verified paid order."""

    order_id = _normalize(order.get("_id"))
    if _normalize(order.get("item_type")).lower() != "addon":
        raise ValueError("The selected order is not an add-on purchase.")
    if _normalize(order.get("source")).lower() not in AUTHORITATIVE_ORDER_SOURCES:
        raise ValueError("The add-on order source is not authoritative.")
    if _normalize(order.get("status")).lower() not in PAID_ORDER_STATUSES:
        raise ValueError("The add-on order is not paid.")
    if not order.get("payment_verified_at"):
        raise ValueError("Verify the Stripe payment before activating the add-on.")
    project_id = _normalize(order.get("project_id"))
    if not project_id:
        raise ValueError("The paid add-on order is not linked to a project.")

    addon_code = _order_addon_code(order)
    if not get_addon(addon_code):
        raise ValueError("The paid order does not contain a known catalog add-on.")
    if addon_code in NFT_ADDON_CODES:
        raise ValueError("Paid NFT credits are consumed by the mint workflow, not activated as service add-ons.")
    entitlement = _entitlement(project_id)
    if _normalize(order.get("fulfillment_status")) == FULFILLMENT_COMPLETE:
        current_addons = {
            normalize_addon_code(value) for value in entitlement.get("active_addons") or []
        }
        if addon_code in current_addons:
            return {
                "order_id": order_id,
                "project_id": project_id,
                "addon_code": addon_code,
                "already_active": True,
                "fulfillment_status": FULFILLMENT_COMPLETE,
            }

    project = _project(project_id)
    package_code = normalize_package_code(
        project.get("package_code") or project.get("package_slug") or project.get("package_type")
    )
    if not can_purchase_addon(package_code, addon_code):
        raise ValueError("The purchased add-on is incompatible with the project's current package.")

    before_addons = [normalize_addon_code(value) for value in entitlement.get("active_addons") or []]
    active_addons = list(dict.fromkeys([*before_addons, addon_code]))
    resolved = resolve_project_entitlements(package_code, active_addons)
    now = datetime.now(UTC)
    paid_sources = list(entitlement.get("paid_addon_sources") or [])
    if not any(_normalize(item.get("order_id")) == order_id for item in paid_sources if isinstance(item, dict)):
        paid_sources.append(
            {
                "order_id": order_id,
                "addon_code": addon_code,
                "stripe_session_id": _normalize(order.get("stripe_session_id")) or None,
                "stripe_payment_intent_id": _normalize(order.get("stripe_payment_intent_id")) or None,
                "stripe_subscription_id": _normalize(order.get("stripe_subscription_id")) or None,
                "activated_at": now,
                "activated_by": _normalize_email((actor or {}).get("email")) or None,
            }
        )

    database = _db()
    database["project_entitlements"].update_one(
        {"_id": entitlement["_id"]},
        {
            "$set": {
                "active_addons": active_addons,
                "resolved_entitlements": resolved,
                "paid_addon_sources": paid_sources,
                "updated_at": now,
            }
        },
    )
    database["orders"].update_one(
        {"_id": order["_id"]},
        {
            "$set": {
                "paid_addon_verified": True,
                "addon_entitlement_status": "active",
                "addon_activated_at": now,
                "addon_activated_by": _normalize_email((actor or {}).get("email")) or None,
                "fulfillment_status": FULFILLMENT_COMPLETE,
                "fulfillment_completed_at": now,
                "fulfillment_completed_by": _normalize_email((actor or {}).get("email")) or None,
            }
        },
    )
    write_audit_log(
        actor_user_id=_normalize((actor or {}).get("_id") or (actor or {}).get("id")) or None,
        actor_email=_normalize_email((actor or {}).get("email")) or None,
        actor_name=_normalize((actor or {}).get("full_name") or (actor or {}).get("name")) or None,
        action="paid_addon.activate_from_verified_order",
        target_type="order",
        target_id=order_id,
        before={"active_addons": before_addons},
        after={"active_addons": active_addons, "addon_code": addon_code},
        context={
            "project_id": project_id,
            "reason": _normalize(reason),
            "idempotency_key": _normalize(idempotency_key),
            "payment_source": _normalize(order.get("source")),
        },
    )
    return {
        "order_id": order_id,
        "project_id": project_id,
        "addon_code": addon_code,
        "activated": True,
        "fulfillment_status": FULFILLMENT_COMPLETE,
        "active_addons": active_addons,
    }


def revoke_paid_addon_access(
    *,
    order: dict[str, Any],
    actor: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    """Remove add-on access unless another authoritative paid order supports it."""

    project_id = _normalize(order.get("project_id"))
    addon_code = _order_addon_code(order)
    if not project_id or not addon_code or addon_code in NFT_ADDON_CODES:
        return {"revoked": False, "reason": "not_an_active_service_addon"}

    order_id = order.get("_id")
    replacement = _db()["orders"].find_one(
        {
            "_id": {"$ne": order_id},
            "project_id": {"$in": _id_candidates(project_id)},
            "item_type": "addon",
            "source": {"$in": sorted(AUTHORITATIVE_ORDER_SOURCES)},
            "status": {"$in": sorted(PAID_ORDER_STATUSES)},
            "addon_code": addon_code,
            "addon_entitlement_status": "active",
        }
    )
    if replacement:
        return {"revoked": False, "reason": "another_paid_order_supports_addon"}

    entitlement = _entitlement(project_id)
    package_code = normalize_package_code(entitlement.get("package_code"))
    active_addons = [
        normalize_addon_code(value)
        for value in entitlement.get("active_addons") or []
        if normalize_addon_code(value) != addon_code
    ]
    paid_sources = [
        item
        for item in entitlement.get("paid_addon_sources") or []
        if not isinstance(item, dict) or _normalize(item.get("order_id")) != _normalize(order_id)
    ]
    _db()["project_entitlements"].update_one(
        {"_id": entitlement["_id"]},
        {
            "$set": {
                "active_addons": active_addons,
                "resolved_entitlements": resolve_project_entitlements(package_code, active_addons),
                "paid_addon_sources": paid_sources,
                "updated_at": datetime.now(UTC),
            }
        },
    )
    write_audit_log(
        actor_user_id=_normalize((actor or {}).get("_id") or (actor or {}).get("id")) or None,
        actor_email=_normalize_email((actor or {}).get("email")) or None,
        actor_name=_normalize((actor or {}).get("full_name") or (actor or {}).get("name")) or None,
        action="paid_addon.revoke_access",
        target_type="order",
        target_id=_normalize(order_id),
        before={"active_addons": list(entitlement.get("active_addons") or [])},
        after={"active_addons": active_addons, "addon_code": addon_code},
        context={"project_id": project_id, "reason": _normalize(reason)},
    )
    return {"revoked": True, "addon_code": addon_code, "active_addons": active_addons}


def revoke_refunded_paid_addon(*, order: dict[str, Any], actor: dict[str, Any] | None) -> dict[str, Any]:
    """Remove fully refunded add-on access unless another paid order supports it."""

    return revoke_paid_addon_access(
        order=order,
        actor=actor,
        reason="governed_full_refund",
    )


def _stripe_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = ((event.get("data") or {}).get("object") or {}) if isinstance(event, dict) else {}
    return payload if isinstance(payload, dict) else {}


def _event_is_paid_addon(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata") or {}
    return _normalize(metadata.get("item_type")).lower() == "addon"


def sync_paid_addon_subscription_event(event: dict[str, Any]) -> dict[str, Any]:
    """Apply Stripe subscription lifecycle truth to a recurring add-on order."""

    payload = _stripe_event_payload(event)
    subscription_id = _normalize(payload.get("id"))
    if not subscription_id:
        return {"matched": False, "updated": False, "reason": "missing_subscription_id"}
    order = _db()["orders"].find_one(
        {"stripe_subscription_id": subscription_id, "item_type": "addon"}
    )
    if not isinstance(order, dict):
        return {
            "matched": _event_is_paid_addon(payload),
            "updated": False,
            "reason": "paid_addon_order_not_found" if _event_is_paid_addon(payload) else "not_paid_addon_subscription",
            "subscription_id": subscription_id,
        }

    event_type = _normalize(event.get("type")).lower()
    stripe_status = _normalize(payload.get("status")).lower()
    if event_type == "customer.subscription.deleted":
        stripe_status = "canceled"
    now = datetime.now(UTC)
    update: dict[str, Any] = {
        "addon_subscription_status": stripe_status or "unknown",
        "addon_subscription_cancel_at_period_end": bool(payload.get("cancel_at_period_end")),
        "addon_subscription_updated_at": now,
    }
    access_result: dict[str, Any] = {"revoked": False, "reason": "subscription_remains_active"}
    if stripe_status in {"canceled", "cancelled", "incomplete_expired", "paused", "unpaid"}:
        update.update(
            {
                "addon_entitlement_status": "revoked",
                "addon_subscription_canceled_at": now,
            }
        )
        access_result = revoke_paid_addon_access(
            order=order,
            actor={"email": "stripe-webhook@tomboflight.system", "full_name": "Stripe Webhook"},
            reason=f"stripe_subscription_{stripe_status}",
        )
    elif stripe_status == "active" and _normalize(order.get("addon_entitlement_status")) == "revoked":
        access_result = activate_paid_addon_order(
            order=order,
            actor={"email": "stripe-webhook@tomboflight.system", "full_name": "Stripe Webhook"},
            reason="stripe_subscription_reactivated",
            idempotency_key=f"stripe-subscription:{subscription_id}:active",
        )
    _db()["orders"].update_one({"_id": order["_id"]}, {"$set": update})
    return {
        "matched": True,
        "updated": True,
        "order_id": _normalize(order.get("_id")),
        "project_id": _normalize(order.get("project_id")) or None,
        "subscription_id": subscription_id,
        "subscription_status": stripe_status or "unknown",
        "access_result": access_result,
        "type": "paid_addon_subscription",
    }


def sync_paid_addon_invoice_event(event: dict[str, Any]) -> dict[str, Any]:
    """Record invoice payment state for an existing recurring add-on order."""

    payload = _stripe_event_payload(event)
    subscription = payload.get("subscription")
    if not subscription:
        subscription = (
            ((payload.get("parent") or {}).get("subscription_details") or {}).get("subscription")
        )
    if isinstance(subscription, dict):
        subscription = subscription.get("id")
    subscription_id = _normalize(subscription)
    if not subscription_id:
        return {"matched": False, "updated": False, "reason": "missing_subscription_id"}
    order = _db()["orders"].find_one(
        {"stripe_subscription_id": subscription_id, "item_type": "addon"}
    )
    if not isinstance(order, dict):
        return {"matched": False, "updated": False, "reason": "not_paid_addon_invoice"}
    event_type = _normalize(event.get("type")).lower()
    invoice_status = "active" if event_type == "invoice.paid" else "past_due"
    now = datetime.now(UTC)
    payment_intent = payload.get("payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id")
    if not payment_intent:
        for invoice_payment in ((payload.get("payments") or {}).get("data") or []):
            payment = (invoice_payment or {}).get("payment") or {}
            candidate = payment.get("payment_intent")
            if isinstance(candidate, dict):
                candidate = candidate.get("id")
            if _normalize(candidate):
                payment_intent = candidate
                break
    update = {
        "addon_subscription_status": invoice_status,
        "addon_subscription_invoice_status": _normalize(payload.get("status")) or None,
        "addon_subscription_invoice_id": _normalize(payload.get("id")) or None,
        "addon_subscription_updated_at": now,
    }
    if _normalize(payment_intent):
        update["stripe_payment_intent_id"] = _normalize(payment_intent)
    if isinstance(payload.get("amount_paid"), (int, float)) and not isinstance(payload.get("amount_paid"), bool):
        update["addon_subscription_last_amount_paid_cents"] = int(payload.get("amount_paid") or 0)
    _db()["orders"].update_one({"_id": order["_id"]}, {"$set": update})
    invoice_id = _normalize(payload.get("id"))
    if (
        invoice_status == "active"
        and _normalize(payload.get("billing_reason")).lower() in {"subscription_cycle", "subscription_update"}
        and invoice_id
        and not _db()["finance_events"].find_one(
            {"event_type": "payment_captured", "stripe_invoice_id": invoice_id}
        )
    ):
        amount_paid_cents = int(payload.get("amount_paid") or 0)
        _db()["finance_events"].insert_one(
            {
                "event_id": f"fin_{uuid4().hex}",
                "event_key": f"stripe_invoice_payment|{invoice_id}",
                "event_type": "payment_captured",
                "order_id": order.get("_id"),
                "project_id": order.get("project_id"),
                "customer_email": _normalize_email(order.get("email")) or None,
                "amount": round(amount_paid_cents / 100, 2),
                "amount_cents": amount_paid_cents,
                "currency": _normalize(payload.get("currency") or order.get("currency")) or "usd",
                "stripe_invoice_id": invoice_id,
                "stripe_payment_intent_id": _normalize(payment_intent) or None,
                "occurred_at": now,
                "source": "stripe_webhook",
                "details": {"billing_reason": _normalize(payload.get("billing_reason"))},
            }
        )
    access_result: dict[str, Any] = {"revoked": False, "reason": "invoice_state_recorded"}
    if invoice_status == "active" and _normalize(order.get("addon_entitlement_status")) == "revoked":
        access_result = activate_paid_addon_order(
            order={**order, **update},
            actor={"email": "stripe-webhook@tomboflight.system", "full_name": "Stripe Webhook"},
            reason="stripe_subscription_invoice_paid",
            idempotency_key=f"stripe-invoice:{_normalize(payload.get('id'))}:paid",
        )
    return {
        "matched": True,
        "updated": True,
        "order_id": _normalize(order.get("_id")),
        "subscription_id": subscription_id,
        "subscription_status": invoice_status,
        "access_result": access_result,
        "type": "paid_addon_subscription",
    }
