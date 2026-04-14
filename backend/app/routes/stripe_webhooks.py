"""
Stripe Webhooks — Tomb of Light

Endpoint:
  POST /webhooks/stripe
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import stripe
from fastapi import APIRouter, HTTPException, Request, status
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.config import settings
from app.database import get_database
from app.services.maintenance_subscription_service import (
    sync_maintenance_checkout_event,
    sync_maintenance_invoice_event,
    sync_maintenance_subscription_event,
)
from app.services.order_service import upsert_order_from_stripe_event

try:
    from stripe.error import SignatureVerificationError  # type: ignore
except Exception:  # pragma: no cover
    SignatureVerificationError = Exception  # type: ignore


router = APIRouter(prefix="/webhooks", tags=["Stripe Webhooks"])
logger = logging.getLogger(__name__)


def _require_setting(value: str, name: str) -> str:
    value = (value or "").strip()
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value


def ensure_stripe_event_indexes() -> None:
    db = get_database()
    events_col = db["stripe_events"]
    try:
        events_col.create_index(
            [("event_id", 1)],
            name="event_id_1",
            unique=True,
            sparse=True,
        )
    except OperationFailure:
        return


def _build_event_audit_record(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    data_object = ((event.get("data") or {}).get("object") or {})
    request_data = event.get("request") or {}
    return {
        "event_id": event.get("id"),
        "type": event.get("type", "unknown"),
        "livemode": bool(event.get("livemode", False)),
        "created": event.get("created"),
        "api_version": event.get("api_version"),
        "account": event.get("account"),
        "object_id": data_object.get("id"),
        "object_type": data_object.get("object"),
        "customer_id": data_object.get("customer"),
        "subscription_id": data_object.get("subscription"),
        "payment_intent_id": data_object.get("payment_intent"),
        "checkout_session_id": data_object.get("id")
        if str(data_object.get("object") or "").strip() == "checkout.session"
        else None,
        "request_id": request_data.get("id"),
        "request_idempotency_key": request_data.get("idempotency_key"),
        "received_at": now,
    }


def _claim_event_processing(
    events_col: Collection[dict[str, Any]],
    *,
    event: dict[str, Any],
    now: datetime,
) -> tuple[bool, str]:
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        return True, ""

    try:
        events_col.update_one(
            {"event_id": event_id},
            {"$setOnInsert": _build_event_audit_record(event, now)},
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    claim_token = str(uuid4())
    claimed = events_col.find_one_and_update(
        {
            "event_id": event_id,
            "processed_at": {"$exists": False},
            "processing_claim": {"$exists": False},
        },
        {
            "$set": {
                "processing_claim": claim_token,
                "processing_started_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if claimed:
        return True, claim_token
    return False, ""


def _mark_event_processed(
    events_col: Collection[dict[str, Any]],
    *,
    event_id: str,
    claim_token: str,
    order_result: dict[str, Any],
    maintenance_result: dict[str, Any],
    now: datetime,
) -> None:
    if not event_id:
        return
    events_col.update_one(
        {
            "event_id": event_id,
            "processing_claim": claim_token,
        },
        {
            "$set": {
                "processed_at": now,
                "processing_finished_at": now,
                "order_result": {
                    "order_id": order_result.get("order_id"),
                    "error": order_result.get("error"),
                    "type": order_result.get("type"),
                },
                "maintenance_result": {
                    "updated": bool(maintenance_result.get("updated")),
                    "error": maintenance_result.get("error"),
                    "type": maintenance_result.get("type"),
                },
            },
            "$unset": {"processing_claim": ""},
        },
    )


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    payload_bytes: bytes = await request.body()
    sig_header: Optional[str] = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    stripe.api_key = _require_setting(settings.stripe_secret_key, "stripe_secret_key")
    endpoint_secret = _require_setting(
        settings.stripe_webhook_secret, "stripe_webhook_secret"
    )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload_bytes,
            sig_header=sig_header,
            secret=endpoint_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    db = get_database()
    events_col = db["stripe_events"]

    event_id = str(event.get("id") or "").strip()
    event_type = event.get("type", "unknown")
    now = datetime.now(timezone.utc)

    should_process, claim_token = _claim_event_processing(
        events_col,
        event=event,
        now=now,
    )
    if not should_process:
        logger.info(
            "Stripe webhook duplicate delivery ignored",
            extra={"event_id": event_id, "event_type": event_type},
        )
        return {
            "received": True,
            "duplicate": True,
            "type": event_type,
            "order": {"order_id": None, "duplicate": True},
            "maintenance": {"updated": False, "duplicate": True},
        }

    order_result: Dict[str, Any] = {"order_id": None}
    maintenance_result: Dict[str, Any] = {"updated": False}

    # Order upsert currently maps Stripe Checkout sessions to orders.
    if event_type == "checkout.session.completed":
        try:
            order_result = upsert_order_from_stripe_event(event)
        except Exception:
            logger.error("Stripe checkout order upsert failed", exc_info=True)
            order_result = {"order_id": None, "error": "order_upsert_failed", "type": event_type}
        try:
            maintenance_result = sync_maintenance_checkout_event(event)
        except Exception:
            logger.error("Stripe checkout maintenance sync failed", exc_info=True)
            maintenance_result = {"updated": False, "error": "maintenance_checkout_sync_failed", "type": event_type}

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        try:
            maintenance_result = sync_maintenance_subscription_event(event)
        except Exception:
            logger.error("Stripe subscription maintenance sync failed", exc_info=True)
            maintenance_result = {"updated": False, "error": "maintenance_subscription_sync_failed", "type": event_type}

    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        try:
            maintenance_result = sync_maintenance_invoice_event(event)
        except Exception:
            logger.error("Stripe invoice maintenance sync failed", exc_info=True)
            maintenance_result = {"updated": False, "error": "maintenance_invoice_sync_failed", "type": event_type}

    _mark_event_processed(
        events_col,
        event_id=event_id,
        claim_token=claim_token,
        order_result=order_result,
        maintenance_result=maintenance_result,
        now=datetime.now(timezone.utc),
    )

    logger.info(
        "Stripe webhook processed",
        extra={
            "event_id": event_id,
            "event_type": event_type,
            "order_result": order_result,
            "maintenance_result": maintenance_result,
        },
    )

    return {
        "received": True,
        "type": event_type,
        "order": order_result,
        "maintenance": maintenance_result,
    }
