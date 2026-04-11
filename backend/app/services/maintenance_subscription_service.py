from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.database import get_database
from app.services.project_entitlement_service import update_project_entitlement_maintenance


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromtimestamp(int(value), UTC)
    except Exception:
        return None


def _metadata_project_id(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") or {}
    return _normalize(
        metadata.get("project_id")
        or metadata.get("upgrade_project_id")
        or metadata.get("existing_project_id")
        or metadata.get("target_project_id")
    )


def _find_project_id_by_subscription_id(subscription_id: str) -> str:
    db = get_database()
    if db is None:
        return ""

    entitlement = db["project_entitlements"].find_one(
        {"maintenance_stripe_subscription_id": subscription_id},
        {"project_id": 1},
    )
    return _normalize((entitlement or {}).get("project_id"))


def sync_maintenance_checkout_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = ((event.get("data") or {}).get("object") or {}) if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        return {"updated": False, "reason": "invalid_payload"}

    mode = _normalize(payload.get("mode")).lower()
    if mode != "subscription":
        return {"updated": False, "reason": "not_subscription_checkout"}

    project_id = _metadata_project_id(payload)
    if not project_id:
        return {"updated": False, "reason": "missing_project_id"}

    subscription_id = _normalize(payload.get("subscription"))
    customer_id = _normalize(payload.get("customer"))
    created_at = _to_datetime(payload.get("created")) or datetime.now(UTC)
    scheduled_start = created_at + timedelta(days=30)

    updated = update_project_entitlement_maintenance(
        project_id=project_id,
        maintenance_plan="monthly",
        maintenance_status="scheduled",
        maintenance_scheduled_start_at=scheduled_start,
        maintenance_stripe_subscription_id=subscription_id or None,
        maintenance_stripe_customer_id=customer_id or None,
        maintenance_stripe_status="incomplete",
    )
    return {
        "updated": bool(updated),
        "project_id": project_id,
        "subscription_id": subscription_id or None,
    }


def sync_maintenance_subscription_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = ((event.get("data") or {}).get("object") or {}) if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        return {"updated": False, "reason": "invalid_payload"}

    subscription_id = _normalize(payload.get("id"))
    if not subscription_id:
        return {"updated": False, "reason": "missing_subscription_id"}

    project_id = _metadata_project_id(payload) or _find_project_id_by_subscription_id(subscription_id)
    if not project_id:
        return {"updated": False, "reason": "missing_project_id"}

    status_value = _normalize(payload.get("status")).lower()
    cancel_at_period_end = bool(payload.get("cancel_at_period_end"))
    current_period_start = _to_datetime(payload.get("current_period_start"))
    current_period_end = _to_datetime(payload.get("current_period_end"))
    customer_id = payload.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")

    maintenance_status = "scheduled"
    if status_value in {"active", "trialing"}:
        maintenance_status = "active"
    elif status_value in {"past_due", "unpaid", "incomplete_expired"}:
        maintenance_status = "past_due"
    elif status_value in {"canceled", "cancelled"}:
        maintenance_status = "canceled"
    elif cancel_at_period_end and status_value == "active":
        maintenance_status = "active"

    updated = update_project_entitlement_maintenance(
        project_id=project_id,
        maintenance_plan="yearly" if _normalize(payload.get("interval")) == "year" else "monthly",
        maintenance_status=maintenance_status,
        maintenance_started_at=current_period_start,
        maintenance_current_period_start=current_period_start,
        maintenance_renews_at=current_period_end,
        maintenance_current_period_end=current_period_end,
        maintenance_stripe_subscription_id=subscription_id,
        maintenance_stripe_customer_id=_normalize(customer_id) or None,
        maintenance_stripe_status=status_value or None,
    )
    return {
        "updated": bool(updated),
        "project_id": project_id,
        "subscription_id": subscription_id,
        "maintenance_status": maintenance_status,
    }


def sync_maintenance_invoice_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = ((event.get("data") or {}).get("object") or {}) if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        return {"updated": False, "reason": "invalid_payload"}

    subscription_id = _normalize(payload.get("subscription"))
    if not subscription_id:
        return {"updated": False, "reason": "missing_subscription_id"}

    project_id = _metadata_project_id(payload) or _find_project_id_by_subscription_id(subscription_id)
    if not project_id:
        return {"updated": False, "reason": "missing_project_id"}

    event_type = _normalize(event.get("type")).lower()
    maintenance_status = "active" if event_type == "invoice.paid" else "past_due"

    updated = update_project_entitlement_maintenance(
        project_id=project_id,
        maintenance_status=maintenance_status,
        maintenance_stripe_subscription_id=subscription_id,
        maintenance_stripe_status=maintenance_status,
    )
    return {
        "updated": bool(updated),
        "project_id": project_id,
        "subscription_id": subscription_id,
        "maintenance_status": maintenance_status,
    }
