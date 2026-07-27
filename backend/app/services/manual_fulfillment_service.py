"""Manual fulfillment queue for Stripe-verified paid orders.

Sales stay open: customers pay through Stripe-hosted checkout and payment is
verified by webhook or server-side session retrieval. Package provisioning is
then completed manually by an authorized administrator from this queue.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional, cast

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services import order_service
from app.services.order_service import (
    AUTHORITATIVE_ORDER_SOURCES,
    FULFILLMENT_COMPLETE,
    FULFILLMENT_ESCALATED,
    FULFILLMENT_IN_PROGRESS,
    FULFILLMENT_PENDING,
    OPEN_FULFILLMENT_STATUSES,
    PAID_ORDER_STATUSES,
)

logger = logging.getLogger(__name__)

FULFILLMENT_ACTIONS = {
    "verify_payment",
    "start_fulfillment",
    "assign_package",
    "complete_fulfillment",
    "escalate_mismatch",
}


def _db() -> Database:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    return cast(Database, db)


def _orders() -> Collection:
    return _db()["orders"]


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _to_object_id(value: Any) -> Optional[ObjectId]:
    raw = _normalize(value)
    if not raw or not ObjectId.is_valid(raw):
        return None
    return ObjectId(raw)


def _actor_fields(admin_user: dict[str, Any]) -> dict[str, str]:
    return {
        "actor_user_id": _normalize(admin_user.get("_id") or admin_user.get("id")),
        "actor_email": _normalize(admin_user.get("email")).lower(),
        "actor_name": _normalize(admin_user.get("full_name") or admin_user.get("name")),
    }


def _next_required_action(order: dict[str, Any]) -> str:
    fulfillment_status = _normalize(order.get("fulfillment_status"))
    if fulfillment_status == FULFILLMENT_COMPLETE:
        return "none"
    if fulfillment_status == FULFILLMENT_ESCALATED:
        return "resolve_payment_mismatch"
    if not order.get("payment_verified_at"):
        return "verify_payment"
    if not order.get("project_id"):
        return "assign_purchased_package"
    return "complete_fulfillment"


def _entitlement_status_for_project(project_id: Any) -> str:
    oid = _to_object_id(project_id)
    if oid is None:
        return "no_project"
    entitlement = _db()["project_entitlements"].find_one(
        {"project_id": oid}, sort=[("created_at", -1)]
    ) or _db()["project_entitlements"].find_one({"project_id": str(oid)})
    if not entitlement:
        return "missing"
    return _normalize(entitlement.get("status")) or "active"


def _serialize_queue_item(order: dict[str, Any]) -> dict[str, Any]:
    user = None
    user_oid = _to_object_id(order.get("user_id"))
    if user_oid is not None:
        user = _db()["users"].find_one({"_id": user_oid})
    project_id = order.get("project_id")
    created_at = order.get("created_at")
    return {
        "order_id": str(order.get("_id")),
        "customer_name": _normalize((user or {}).get("full_name") or (user or {}).get("name")),
        "email": _normalize(order.get("email")),
        "stripe_session_id": _normalize(order.get("stripe_session_id")) or None,
        "stripe_payment_intent_id": _normalize(order.get("stripe_payment_intent_id")) or None,
        "payment_status": _normalize(order.get("status")),
        "payment_verified": bool(order.get("payment_verified_at")),
        "payment_verified_at": order.get("payment_verified_at"),
        "amount_label": _normalize(order.get("price_label")),
        "currency": _normalize(order.get("currency")) or "usd",
        "package_code": _normalize(order.get("package_code") or order.get("package_slug")),
        "package_name": _normalize(order.get("package_name")),
        "billing_plan": _normalize(order.get("billing_plan")) or "one_time",
        "item_type": _normalize(order.get("item_type")) or "package",
        "coupon": _normalize(order.get("coupon") or order.get("campaign")) or None,
        "payment_date": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "fulfillment_status": _normalize(order.get("fulfillment_status")) or FULFILLMENT_PENDING,
        "linked_user_id": str(user_oid) if user_oid is not None else None,
        "linked_project_id": str(project_id) if project_id else None,
        "entitlement_status": _entitlement_status_for_project(project_id),
        "assigned_operator": _normalize(order.get("fulfillment_operator_email")) or None,
        "next_required_action": _next_required_action(order),
        "source": _normalize(order.get("source")),
    }


def list_manual_fulfillment_queue(*, limit: int = 100) -> dict[str, Any]:
    query = {
        "status": {"$in": sorted(PAID_ORDER_STATUSES)},
        "source": {"$in": sorted(AUTHORITATIVE_ORDER_SOURCES)},
        "fulfillment_status": {"$in": sorted(OPEN_FULFILLMENT_STATUSES)},
    }
    cursor = _orders().find(query).sort("created_at", -1).limit(max(1, min(limit, 500)))
    items = [_serialize_queue_item(order) for order in cursor]
    return {
        "queue": "paid_manual_fulfillment_required",
        "count": len(items),
        "items": items,
    }


def _require_open_order(order_id: str) -> dict[str, Any]:
    oid = _to_object_id(order_id)
    if oid is None:
        raise ValueError("Invalid order id.")
    order = _orders().find_one({"_id": oid})
    if not order:
        raise ValueError("Order not found.")
    if _normalize(order.get("status")).lower() not in PAID_ORDER_STATUSES:
        raise ValueError("Order is not a verified paid order.")
    if _normalize(order.get("source")).lower() not in AUTHORITATIVE_ORDER_SOURCES:
        raise ValueError("Order payment source is not authoritative.")
    return order


def _write_fulfillment_audit(
    admin_user: dict[str, Any],
    *,
    action: str,
    order: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
    idempotency_key: str,
) -> None:
    write_audit_log(
        **_actor_fields(admin_user),
        action=f"manual_fulfillment.{action}",
        target_type="order",
        target_id=str(order.get("_id")),
        before=before,
        after=after,
        context={
            "queue": "paid_manual_fulfillment_required",
            "reason": reason,
            "idempotency_key": idempotency_key,
            "stripe_session_id": _normalize(order.get("stripe_session_id")) or None,
            "package_code": _normalize(order.get("package_code")),
            "email": _normalize(order.get("email")),
        },
    )


def _verify_payment(admin_user: dict[str, Any], order: dict[str, Any], reason: str, idempotency_key: str) -> dict[str, Any]:
    if order.get("payment_verified_at"):
        return {"order_id": str(order["_id"]), "already_verified": True, "verified": True}

    session_id = _normalize(order.get("stripe_session_id"))
    verification: dict[str, Any] = {"method": None, "verified": False}
    if _normalize(order.get("source")).lower() == "admin_manual":
        verification = {
            "method": "protected_manual_finance_workflow",
            "verified": True,
            "authorization_source": _normalize(order.get("manual_authorization_source")) or None,
        }
    elif session_id:
        session = order_service._retrieve_checkout_session(session_id)
        payment_status = _normalize(session.get("payment_status")).lower()
        if payment_status != "paid":
            raise ValueError(f"Stripe reports payment_status '{payment_status or 'unknown'}' for this session.")
        verification = {
            "method": "stripe_session_retrieval",
            "verified": True,
            "stripe_payment_status": payment_status,
            "amount_total": session.get("amount_total"),
            "currency": _normalize(session.get("currency")) or None,
            "payment_intent": _normalize(session.get("payment_intent")) or None,
        }
    else:
        raise ValueError("Order has no Stripe session and no protected manual authorization; cannot verify payment.")

    now = datetime.now(UTC)
    update: dict[str, Any] = {
        "payment_verified_at": now,
        "payment_verified_by": _normalize(admin_user.get("email")).lower(),
        "payment_verification": verification,
    }
    if verification.get("amount_total") is not None:
        update["amount_total_cents"] = verification["amount_total"]
    if verification.get("currency"):
        update["currency"] = verification["currency"]
    if verification.get("payment_intent"):
        update["stripe_payment_intent_id"] = verification["payment_intent"]
    _orders().update_one({"_id": order["_id"]}, {"$set": update})
    _write_fulfillment_audit(
        admin_user,
        action="verify_payment",
        order=order,
        before={"payment_verified": False},
        after={"payment_verified": True, "verification": verification},
        reason=reason,
        idempotency_key=idempotency_key,
    )
    return {"order_id": str(order["_id"]), "verified": True, "verification": verification}


def _start_fulfillment(admin_user: dict[str, Any], order: dict[str, Any], reason: str, idempotency_key: str) -> dict[str, Any]:
    current = _normalize(order.get("fulfillment_status"))
    operator = _normalize(admin_user.get("email")).lower()
    if current == FULFILLMENT_IN_PROGRESS and _normalize(order.get("fulfillment_operator_email")) == operator:
        return {"order_id": str(order["_id"]), "fulfillment_status": current, "already_in_progress": True}
    if current == FULFILLMENT_COMPLETE:
        raise ValueError("Order fulfillment is already complete.")
    update = {
        "fulfillment_status": FULFILLMENT_IN_PROGRESS,
        "fulfillment_operator_email": operator,
        "fulfillment_started_at": datetime.now(UTC),
    }
    _orders().update_one({"_id": order["_id"]}, {"$set": update})
    _write_fulfillment_audit(
        admin_user,
        action="start_fulfillment",
        order=order,
        before={"fulfillment_status": current or FULFILLMENT_PENDING},
        after={"fulfillment_status": FULFILLMENT_IN_PROGRESS, "operator": operator},
        reason=reason,
        idempotency_key=idempotency_key,
    )
    return {"order_id": str(order["_id"]), "fulfillment_status": FULFILLMENT_IN_PROGRESS}


def _assign_package(admin_user: dict[str, Any], order: dict[str, Any], reason: str, idempotency_key: str) -> dict[str, Any]:
    if not order.get("payment_verified_at"):
        raise ValueError("Verify payment before provisioning the purchased package.")
    if order.get("project_id"):
        return {
            "order_id": str(order["_id"]),
            "already_provisioned": True,
            "project_id": str(order["project_id"]),
        }
    user_oid = _to_object_id(order.get("user_id"))
    user = _db()["users"].find_one({"_id": user_oid}) if user_oid is not None else None
    if not user:
        raise ValueError("Order is not linked to a customer account. Link or create the customer first.")

    package_code = _normalize(order.get("package_code") or order.get("package_slug"))
    order_doc = order_service._attach_project_to_paid_package_order(
        order_id=order["_id"],
        order_doc=dict(order),
        user=user,
        package_code=package_code,
        package_name=_normalize(order.get("package_name")),
        stripe_session_id=_normalize(order.get("stripe_session_id")) or None,
        stripe_payment_link_id=_normalize(order.get("stripe_payment_link_id")) or None,
    )
    order_service._trigger_package_provisioning()
    project_id = str(order_doc.get("project_id")) if order_doc.get("project_id") else None
    _orders().update_one(
        {"_id": order["_id"]},
        {
            "$set": {
                "fulfillment_status": FULFILLMENT_IN_PROGRESS,
                "fulfillment_operator_email": _normalize(admin_user.get("email")).lower(),
                "package_provisioned_at": datetime.now(UTC),
                "package_provisioned_by": _normalize(admin_user.get("email")).lower(),
            }
        },
    )
    _write_fulfillment_audit(
        admin_user,
        action="assign_package",
        order=order,
        before={"project_id": None},
        after={"project_id": project_id, "package_code": package_code},
        reason=reason,
        idempotency_key=idempotency_key,
    )
    return {
        "order_id": str(order["_id"]),
        "provisioned": True,
        "project_id": project_id,
        "package_code": package_code,
        "entitlement_status": _entitlement_status_for_project(project_id),
    }


def _complete_fulfillment(admin_user: dict[str, Any], order: dict[str, Any], reason: str, idempotency_key: str) -> dict[str, Any]:
    current = _normalize(order.get("fulfillment_status"))
    if current == FULFILLMENT_COMPLETE:
        return {"order_id": str(order["_id"]), "fulfillment_status": current, "already_complete": True}
    if not order.get("payment_verified_at"):
        raise ValueError("Verify payment before completing fulfillment.")
    if not order.get("project_id"):
        raise ValueError("Assign the purchased package before completing fulfillment.")
    operator = _normalize(admin_user.get("email")).lower()
    update = {
        "fulfillment_status": FULFILLMENT_COMPLETE,
        "fulfillment_completed_at": datetime.now(UTC),
        "fulfillment_completed_by": operator,
        "fulfillment_operator_email": operator,
    }
    _orders().update_one({"_id": order["_id"]}, {"$set": update})
    _write_fulfillment_audit(
        admin_user,
        action="complete_fulfillment",
        order=order,
        before={"fulfillment_status": current or FULFILLMENT_PENDING},
        after={"fulfillment_status": FULFILLMENT_COMPLETE, "operator": operator},
        reason=reason,
        idempotency_key=idempotency_key,
    )
    return {"order_id": str(order["_id"]), "fulfillment_status": FULFILLMENT_COMPLETE}


def _escalate_mismatch(admin_user: dict[str, Any], order: dict[str, Any], reason: str, idempotency_key: str) -> dict[str, Any]:
    current = _normalize(order.get("fulfillment_status"))
    if current == FULFILLMENT_ESCALATED:
        return {"order_id": str(order["_id"]), "fulfillment_status": current, "already_escalated": True}
    update = {
        "fulfillment_status": FULFILLMENT_ESCALATED,
        "fulfillment_escalated_at": datetime.now(UTC),
        "fulfillment_escalated_by": _normalize(admin_user.get("email")).lower(),
        "fulfillment_escalation_reason": reason,
    }
    _orders().update_one({"_id": order["_id"]}, {"$set": update})
    _write_fulfillment_audit(
        admin_user,
        action="escalate_mismatch",
        order=order,
        before={"fulfillment_status": current or FULFILLMENT_PENDING},
        after={"fulfillment_status": FULFILLMENT_ESCALATED},
        reason=reason,
        idempotency_key=idempotency_key,
    )
    return {"order_id": str(order["_id"]), "fulfillment_status": FULFILLMENT_ESCALATED}


def execute_fulfillment_action(
    admin_user: dict[str, Any],
    *,
    order_id: str,
    action: str,
    reason: str = "",
    idempotency_key: str = "",
) -> dict[str, Any]:
    normalized_action = _normalize(action).lower().replace("-", "_")
    if normalized_action not in FULFILLMENT_ACTIONS:
        raise ValueError(f"Unsupported fulfillment action '{action}'.")
    reason = _normalize(reason)
    idempotency_key = _normalize(idempotency_key)
    if not reason:
        raise ValueError("A reason is required for fulfillment actions.")
    if len(idempotency_key) < 8:
        raise ValueError("An idempotency_key of at least 8 characters is required.")

    order = _require_open_order(order_id)

    handlers = {
        "verify_payment": _verify_payment,
        "start_fulfillment": _start_fulfillment,
        "assign_package": _assign_package,
        "complete_fulfillment": _complete_fulfillment,
        "escalate_mismatch": _escalate_mismatch,
    }
    result = handlers[normalized_action](admin_user, order, reason, idempotency_key)
    refreshed = _orders().find_one({"_id": order["_id"]}) or order
    result["item"] = _serialize_queue_item(refreshed)
    return result
