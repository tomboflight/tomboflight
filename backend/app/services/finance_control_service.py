"""Governed CEO billing adjustments, payroll ledger writes, and exports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from bson import ObjectId
from pymongo.database import Database

from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services import paid_addon_service, stripe_admin_operations_service


BILLING_ADJUSTMENT_ACTIONS = frozenset({"refund", "customer_credit", "subscription_discount"})
PAYROLL_ACTIONS = frozenset(
    {"create_draft", "update_draft", "submit_for_review", "approve", "mark_processed", "void"}
)
FINANCE_EXPORT_TYPES = frozenset(
    {
        "monthly_finance_export",
        "tax_export",
        "refund_report",
        "subscription_report",
        "payroll_report",
        "package_performance_report",
    }
)
PRODUCTION_STARTED_STATES = frozenset(
    {
        "build_started",
        "build_ready",
        "in_production",
        "production",
        "quality_review",
        "qa_review",
        "client_review",
        "delivery_complete",
        "delivered",
        "completed",
        "archived",
    }
)
PAID_ORDER_STATES = frozenset({"paid", "complete", "completed", "succeeded"})
AUTHORITATIVE_ORDER_SOURCES = frozenset({"stripe_webhook", "stripe_verified"})


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _now() -> datetime:
    return datetime.now(UTC)


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


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _find_order(order_id: str) -> dict[str, Any]:
    order = _db()["orders"].find_one({"_id": {"$in": _id_candidates(order_id)}})
    if not isinstance(order, dict):
        raise ValueError("Order not found.")
    return order


def _project_for_order(order: dict[str, Any]) -> dict[str, Any] | None:
    project_id = _normalize(order.get("project_id"))
    if not project_id:
        return None
    project = _db()["projects"].find_one({"_id": {"$in": _id_candidates(project_id)}})
    return project if isinstance(project, dict) else None


def _production_started(project: dict[str, Any] | None) -> bool:
    if not project:
        return False
    if any(project.get(field) for field in ("production_started_at", "build_started_at")):
        return True
    states = {
        _normalize(project.get("status")).lower(),
        _normalize(project.get("phase")).lower(),
        _normalize(project.get("workflow_state")).lower(),
        _normalize(project.get("build_status")).lower(),
    }
    return bool(states.intersection(PRODUCTION_STARTED_STATES))


def _order_amount_cents(order: dict[str, Any]) -> int:
    for field in ("amount_total_cents", "amount_cents", "amount_total"):
        value = order.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0, int(value))
    return 0


def preview_billing_adjustment(*, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    order = _find_order(order_id)
    action = _normalize(payload.get("billing_action")).lower()
    if action not in BILLING_ADJUSTMENT_ACTIONS:
        raise ValueError("billing_action must be refund, customer_credit, or subscription_discount.")

    project = _project_for_order(order)
    project_started = _production_started(project)
    order_status = _normalize(order.get("status")).lower()
    order_source = _normalize(order.get("source")).lower()
    amount_cents = int(payload.get("amount_cents") or 0)
    order_amount_cents = _order_amount_cents(order)
    blockers: list[str] = []
    warnings: list[str] = []

    if order_source not in AUTHORITATIVE_ORDER_SOURCES:
        blockers.append("order_payment_source_not_authoritative")
    if order_status not in PAID_ORDER_STATES:
        blockers.append("order_is_not_paid")
    if action == "refund":
        if project_started:
            blockers.append("production_work_has_begun")
        if not _normalize(order.get("stripe_payment_intent_id")):
            blockers.append("stripe_payment_intent_missing")
        if _normalize(order.get("refund_status")).lower() in {"succeeded", "refunded"}:
            blockers.append("order_already_refunded")
        if amount_cents < 0:
            blockers.append("refund_amount_invalid")
        if amount_cents and order_amount_cents and amount_cents > order_amount_cents:
            blockers.append("refund_exceeds_order_total")
        warnings.append("Refunds are prohibited after production work begins.")
    elif action == "customer_credit":
        if amount_cents <= 0:
            blockers.append("credit_amount_required")
        if not _normalize(order.get("email")):
            blockers.append("customer_email_missing")
        warnings.append("This creates Stripe customer balance credit; it does not issue cash.")
    elif action == "subscription_discount":
        if not _normalize(payload.get("subscription_id") or order.get("stripe_subscription_id")):
            blockers.append("subscription_id_required")
        if not _normalize(payload.get("coupon_id")):
            blockers.append("coupon_id_required")
        warnings.append("The referenced Stripe coupon must already be approved and active.")

    return {
        "before": {
            "order_id": _normalize(order.get("_id")),
            "order_status": order_status,
            "order_source": order_source,
            "order_amount_cents": order_amount_cents or None,
            "project_id": _normalize(order.get("project_id")) or None,
            "project_status": _normalize((project or {}).get("status")) or None,
            "project_phase": _normalize((project or {}).get("phase")) or None,
            "production_started": project_started,
        },
        "proposed_after": {
            "billing_action": action,
            "amount_cents": amount_cents or None,
            "subscription_id": _normalize(payload.get("subscription_id") or order.get("stripe_subscription_id")) or None,
            "coupon_id": _normalize(payload.get("coupon_id")) or None,
        },
        "blocked": bool(blockers),
        "blocked_reasons": blockers,
        "warnings": warnings,
    }


def _record_finance_event(
    *,
    event_type: str,
    order: dict[str, Any],
    actor: dict[str, Any] | None,
    amount_cents: int,
    details: dict[str, Any],
) -> str:
    event_id = f"fin_{uuid4().hex}"
    _db()["finance_events"].insert_one(
        {
            "event_id": event_id,
            "event_type": event_type,
            "order_id": order.get("_id"),
            "project_id": order.get("project_id"),
            "customer_email": _normalize_email(order.get("email")) or None,
            "amount": round(amount_cents / 100, 2),
            "amount_cents": amount_cents,
            "currency": _normalize(order.get("currency")) or "usd",
            "actor_user_id": _normalize((actor or {}).get("_id") or (actor or {}).get("id")) or None,
            "actor_email": _normalize_email((actor or {}).get("email")) or None,
            "occurred_at": _now(),
            "details": details,
        }
    )
    return event_id


def _revoke_refunded_package_access(order: dict[str, Any], actor: dict[str, Any] | None) -> dict[str, Any]:
    item_type = _normalize(order.get("item_type")).lower()
    if item_type == "addon":
        return paid_addon_service.revoke_refunded_paid_addon(order=order, actor=actor)
    project_id = _normalize(order.get("project_id"))
    if not project_id:
        return {"revoked": False, "reason": "order_has_no_project"}
    now = _now()
    entitlement_result = _db()["project_entitlements"].update_many(
        {"project_id": {"$in": _id_candidates(project_id)}},
        {
            "$set": {
                "status": "revoked",
                "access_enabled": False,
                "refund_status": "refunded",
                "refunded_at": now,
                "updated_at": now,
            }
        },
    )
    _db()["projects"].update_one(
        {"_id": {"$in": _id_candidates(project_id)}},
        {
            "$set": {
                "status": "payment_refunded",
                "payment_refunded_at": now,
                "updated_at": now,
            }
        },
    )
    return {"revoked": bool(getattr(entitlement_result, "modified_count", 0)), "project_id": project_id}


def apply_billing_adjustment(
    *,
    order_id: str,
    payload: dict[str, Any],
    actor: dict[str, Any] | None,
) -> dict[str, Any]:
    reason = _normalize(payload.get("reason"))
    if len(reason) < 3:
        raise ValueError("A billing adjustment reason is required.")
    if payload.get("confirmed") is not True:
        raise ValueError("Billing adjustment confirmation is required.")
    preview = preview_billing_adjustment(order_id=order_id, payload=payload)
    if preview.get("blocked"):
        raise ValueError("Billing adjustment is blocked: " + ", ".join(preview.get("blocked_reasons") or []))

    order = _find_order(order_id)
    action = _normalize(payload.get("billing_action")).lower()
    idempotency_key = _normalize(payload.get("continuity_idempotency_key"))
    amount_cents = int(payload.get("amount_cents") or 0)
    if action == "refund":
        result = stripe_admin_operations_service.refund_payment(
            actor or {},
            payment_intent_id=_normalize(order.get("stripe_payment_intent_id")),
            amount_cents=amount_cents,
            refund_reason=_normalize(payload.get("refund_reason")) or "requested_by_customer",
            reason=reason,
            confirm=True,
            idempotency_key=idempotency_key,
        )
        refund_amount = int(result.get("amount") or amount_cents or _order_amount_cents(order))
        refund_status = _normalize(result.get("status")).lower() or "pending"
        order_amount = _order_amount_cents(order)
        full_refund = bool(not amount_cents or (order_amount and refund_amount >= order_amount))
        update = {
            "stripe_refund_id": result.get("refund_id"),
            "refund_status": refund_status,
            "refund_amount": round(refund_amount / 100, 2),
            "refund_amount_cents": refund_amount,
            "refunded_at": _now(),
            "refunded_by": _normalize_email((actor or {}).get("email")) or None,
        }
        if refund_status == "succeeded":
            update["status"] = "refunded" if full_refund else "partially_refunded"
        _db()["orders"].update_one({"_id": order["_id"]}, {"$set": update})
        access_result = (
            _revoke_refunded_package_access({**order, **update}, actor)
            if refund_status == "succeeded" and full_refund
            else {"revoked": False, "reason": "partial_or_pending_refund"}
        )
        event_id = _record_finance_event(
            event_type="refund_recorded",
            order=order,
            actor=actor,
            amount_cents=refund_amount,
            details={"stripe_result": result, "full_refund": full_refund, "access_result": access_result},
        )
    elif action == "customer_credit":
        result = stripe_admin_operations_service.create_customer_credit(
            actor or {},
            customer_email=_normalize_email(order.get("email")),
            amount_cents=amount_cents,
            description=_normalize(payload.get("description")) or reason,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        access_result = {"revoked": False, "reason": "credit_does_not_change_access"}
        event_id = _record_finance_event(
            event_type="credit_recorded",
            order=order,
            actor=actor,
            amount_cents=amount_cents,
            details={"stripe_result": result},
        )
    else:
        result = stripe_admin_operations_service.apply_subscription_discount(
            actor or {},
            customer_email=_normalize_email(order.get("email")),
            subscription_id=_normalize(payload.get("subscription_id") or order.get("stripe_subscription_id")),
            coupon_id=_normalize(payload.get("coupon_id")),
            reason=reason,
            idempotency_key=idempotency_key,
        )
        access_result = {"revoked": False, "reason": "discount_does_not_change_access"}
        event_id = _record_finance_event(
            event_type="billing_adjustment",
            order=order,
            actor=actor,
            amount_cents=0,
            details={"stripe_result": result, "adjustment_type": "subscription_discount"},
        )

    write_audit_log(
        actor_user_id=_normalize((actor or {}).get("_id") or (actor or {}).get("id")) or None,
        actor_email=_normalize_email((actor or {}).get("email")) or None,
        actor_name=_normalize((actor or {}).get("full_name") or (actor or {}).get("name")) or None,
        action=f"finance_control.{action}",
        target_type="order",
        target_id=_normalize(order.get("_id")),
        before=preview.get("before"),
        after={"stripe_result": result, "finance_event_id": event_id, "access_result": access_result},
        context={"reason": reason, "idempotency_key": idempotency_key},
    )
    return {
        "order_id": _normalize(order.get("_id")),
        "billing_action": action,
        "stripe_result": result,
        "finance_event_id": event_id,
        "access_result": access_result,
        "failure_count": 0,
    }


def _find_payroll_run(payroll_run_id: str) -> dict[str, Any] | None:
    normalized = _normalize(payroll_run_id)
    if not normalized:
        return None
    query: dict[str, Any] = {"payroll_run_id": normalized}
    if ObjectId.is_valid(normalized):
        query = {"$or": [{"_id": ObjectId(normalized)}, {"payroll_run_id": normalized}]}
    run = _db()["payroll_runs"].find_one(query)
    return run if isinstance(run, dict) else None


def _payroll_total(payload: dict[str, Any]) -> int:
    entries = payload.get("entries") or []
    if entries:
        total = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Each payroll entry must be an object.")
            amount = int(entry.get("amount_cents") or 0)
            if amount < 0:
                raise ValueError("Payroll entry amounts cannot be negative.")
            total += amount
        return total
    return int(payload.get("total_amount_cents") or 0)


def preview_payroll_control(*, payroll_run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = _normalize(payload.get("payroll_action")).lower()
    if action not in PAYROLL_ACTIONS:
        raise ValueError("Unsupported payroll action.")
    existing = _find_payroll_run(payroll_run_id)
    current_status = _normalize((existing or {}).get("status")).lower()
    blockers: list[str] = []
    proposed_status = current_status

    if action == "create_draft":
        if existing:
            blockers.append("payroll_run_already_exists")
        if not _normalize(payload.get("period_start")) or not _normalize(payload.get("period_end")):
            blockers.append("payroll_period_required")
        if _payroll_total(payload) < 0:
            blockers.append("payroll_total_invalid")
        proposed_status = "draft"
    elif not existing:
        blockers.append("payroll_run_not_found")
    elif action == "update_draft":
        if current_status != "draft":
            blockers.append("only_draft_payroll_can_be_updated")
        proposed_status = "draft"
    elif action == "submit_for_review":
        if current_status != "draft":
            blockers.append("only_draft_payroll_can_be_submitted")
        proposed_status = "review"
    elif action == "approve":
        if current_status != "review":
            blockers.append("payroll_must_be_in_review")
        proposed_status = "approved"
    elif action == "mark_processed":
        if current_status != "approved":
            blockers.append("payroll_must_be_approved")
        if not _normalize(payload.get("external_reference")):
            blockers.append("external_payment_reference_required")
        proposed_status = "processed"
    elif action == "void":
        if current_status in {"processed", "completed", "void"}:
            blockers.append("processed_or_void_payroll_cannot_be_voided")
        proposed_status = "void"

    return {
        "before": _serialize(existing) if existing else {},
        "proposed_after": {
            "payroll_run_id": _normalize(payroll_run_id),
            "status": proposed_status,
            "period_start": _normalize(payload.get("period_start") or (existing or {}).get("period_start")) or None,
            "period_end": _normalize(payload.get("period_end") or (existing or {}).get("period_end")) or None,
            "total_amount_cents": _payroll_total(payload) if action in {"create_draft", "update_draft"} else int((existing or {}).get("total_amount_cents") or 0),
            "external_reference": _normalize(payload.get("external_reference")) or None,
        },
        "blocked": bool(blockers),
        "blocked_reasons": blockers,
        "warnings": [
            "Payroll controls maintain the governed payroll ledger; they do not initiate a bank transfer."
        ],
    }


def apply_payroll_control(
    *,
    payroll_run_id: str,
    payload: dict[str, Any],
    actor: dict[str, Any] | None,
) -> dict[str, Any]:
    reason = _normalize(payload.get("reason"))
    if len(reason) < 3:
        raise ValueError("A payroll action reason is required.")
    if payload.get("confirmed") is not True:
        raise ValueError("Payroll action confirmation is required.")
    preview = preview_payroll_control(payroll_run_id=payroll_run_id, payload=payload)
    if preview.get("blocked"):
        raise ValueError("Payroll action is blocked: " + ", ".join(preview.get("blocked_reasons") or []))

    action = _normalize(payload.get("payroll_action")).lower()
    now = _now()
    actor_email = _normalize_email((actor or {}).get("email")) or None
    proposed = dict(preview.get("proposed_after") or {})
    if action == "create_draft":
        document = {
            "payroll_run_id": _normalize(payroll_run_id) or f"payroll_{uuid4().hex}",
            "period_start": proposed.get("period_start"),
            "period_end": proposed.get("period_end"),
            "status": "draft",
            "entries": list(payload.get("entries") or []),
            "total_amount_cents": int(proposed.get("total_amount_cents") or 0),
            "total_amount": round(int(proposed.get("total_amount_cents") or 0) / 100, 2),
            "notes": _normalize(payload.get("notes")) or None,
            "created_at": now,
            "created_by": actor_email,
            "updated_at": now,
        }
        result = _db()["payroll_runs"].insert_one(document)
        stored = {**document, "_id": result.inserted_id}
    else:
        existing = _find_payroll_run(payroll_run_id)
        if not existing:
            raise ValueError("Payroll run not found.")
        update: dict[str, Any] = {"status": proposed.get("status"), "updated_at": now, "updated_by": actor_email}
        if action == "update_draft":
            update.update(
                {
                    "period_start": proposed.get("period_start"),
                    "period_end": proposed.get("period_end"),
                    "entries": list(payload.get("entries") or existing.get("entries") or []),
                    "total_amount_cents": int(proposed.get("total_amount_cents") or 0),
                    "total_amount": round(int(proposed.get("total_amount_cents") or 0) / 100, 2),
                    "notes": _normalize(payload.get("notes")) or existing.get("notes"),
                }
            )
        elif action == "submit_for_review":
            update.update({"submitted_at": now, "submitted_by": actor_email})
        elif action == "approve":
            update.update({"approved_at": now, "approved_by": actor_email})
        elif action == "mark_processed":
            update.update(
                {
                    "processed_at": now,
                    "processed_by": actor_email,
                    "external_reference": _normalize(payload.get("external_reference")),
                }
            )
        elif action == "void":
            update.update({"voided_at": now, "voided_by": actor_email, "void_reason": reason})
        _db()["payroll_runs"].update_one({"_id": existing["_id"]}, {"$set": update})
        stored = {**existing, **update}

    write_audit_log(
        actor_user_id=_normalize((actor or {}).get("_id") or (actor or {}).get("id")) or None,
        actor_email=actor_email,
        actor_name=_normalize((actor or {}).get("full_name") or (actor or {}).get("name")) or None,
        action=f"payroll_control.{action}",
        target_type="payroll_run",
        target_id=_normalize(stored.get("payroll_run_id") or stored.get("_id")),
        before=preview.get("before"),
        after=_serialize(stored),
        context={"reason": reason, "bank_transfer_initiated": False},
    )
    return {
        "payroll_action": action,
        "payroll_run": _serialize(stored),
        "bank_transfer_initiated": False,
        "failure_count": 0,
    }


def _date_query(field: str, period_start: str, period_end: str) -> dict[str, Any]:
    bounds: dict[str, Any] = {}
    for operator, raw in (("$gte", period_start), ("$lte", period_end)):
        normalized = _normalize(raw)
        if not normalized:
            continue
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            if operator == "$lte" and len(normalized) == 10:
                parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            bounds[operator] = parsed
        except ValueError as exc:
            raise ValueError("Export period values must be ISO-8601 dates or datetimes.") from exc
    return {field: bounds} if bounds else {}


def _value_in_export_period(value: Any, period_start: str, period_end: str) -> bool:
    if not period_start and not period_end:
        return True
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=UTC)
    else:
        normalized = _normalize(value)
        if not normalized:
            return False
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
    bounds = (_date_query("value", period_start, period_end).get("value") or {})
    return not (
        (bounds.get("$gte") and parsed < bounds["$gte"])
        or (bounds.get("$lte") and parsed > bounds["$lte"])
    )


def generate_finance_export(
    *,
    report_type: str,
    period_start: str = "",
    period_end: str = "",
    limit: int = 5000,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_type = _normalize(report_type).lower()
    if normalized_type not in FINANCE_EXPORT_TYPES:
        raise ValueError("Unsupported finance export type.")
    database = _db()
    safe_limit = max(1, min(int(limit), 5000))
    records: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    if normalized_type in {"monthly_finance_export", "refund_report", "tax_export"}:
        query = _date_query("occurred_at", period_start, period_end)
        if normalized_type == "refund_report":
            query["event_type"] = "refund_recorded"
        events = list(database["finance_events"].find(query).sort("occurred_at", -1).limit(safe_limit))
        records = [_serialize(item) for item in events]
        summary = {
            "record_count": len(records),
            "total_amount": round(sum(float(item.get("amount") or 0) for item in events), 2),
        }
        if normalized_type == "tax_export":
            summary["filing_ready"] = False
            summary["notice"] = "Operational finance dataset; review with the company tax professional before filing."
    elif normalized_type == "subscription_report":
        query = _date_query("updated_at", period_start, period_end)
        fields = {
            "project_id": 1,
            "user_id": 1,
            "package_code": 1,
            "maintenance_plan": 1,
            "maintenance_status": 1,
            "maintenance_current_period_start": 1,
            "maintenance_current_period_end": 1,
            "maintenance_stripe_subscription_id": 1,
            "updated_at": 1,
        }
        records = [
            _serialize(item)
            for item in database["project_entitlements"].find(query, fields).sort("updated_at", -1).limit(safe_limit)
        ]
        summary = {"record_count": len(records)}
    elif normalized_type == "payroll_report":
        records = [
            _serialize(item)
            for item in database["payroll_runs"].find({}).sort("period_end", -1).limit(safe_limit)
            if _value_in_export_period(item.get("period_end"), period_start, period_end)
        ]
        summary = {
            "record_count": len(records),
            "total_amount": round(sum(float(item.get("total_amount") or 0) for item in records), 2),
        }
    else:
        query = {
            "status": {"$in": sorted(PAID_ORDER_STATES)},
            "source": {"$in": sorted(AUTHORITATIVE_ORDER_SOURCES)},
            **_date_query("created_at", period_start, period_end),
        }
        buckets: dict[str, dict[str, Any]] = {}
        for order in database["orders"].find(query).sort("created_at", -1).limit(safe_limit):
            item_type = _normalize(order.get("item_type")).lower()
            code = _normalize(
                order.get("addon_code") if item_type == "addon" else order.get("package_code")
            ) or "unknown"
            bucket = buckets.setdefault(code, {"product_code": code, "orders": 0, "gross_revenue": 0.0})
            bucket["orders"] += 1
            cents = _order_amount_cents(order)
            bucket["gross_revenue"] += round(cents / 100, 2)
        records = sorted(buckets.values(), key=lambda item: (-int(item["orders"]), item["product_code"]))
        summary = {
            "product_count": len(records),
            "order_count": sum(int(item["orders"]) for item in records),
            "gross_revenue": round(sum(float(item["gross_revenue"]) for item in records), 2),
        }

    export = {
        "generated_at": _now().isoformat(),
        "report_type": normalized_type,
        "format": "json",
        "period_start": _normalize(period_start) or None,
        "period_end": _normalize(period_end) or None,
        "summary": summary,
        "records": records,
        "status": "live",
    }
    if actor:
        write_audit_log(
            actor_user_id=_normalize(actor.get("_id") or actor.get("id")) or None,
            actor_email=_normalize_email(actor.get("email")) or None,
            actor_name=_normalize(actor.get("full_name") or actor.get("name")) or None,
            action="finance_export.generated",
            target_type="finance_report",
            target_id=normalized_type,
            after={"summary": export["summary"], "record_count": len(records)},
            context={
                "period_start": _normalize(period_start) or None,
                "period_end": _normalize(period_end) or None,
                "limit": safe_limit,
            },
        )
    return export
