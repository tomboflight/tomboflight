"""
Stripe Webhooks — Tomb of Light

Endpoint:
  POST /webhooks/stripe
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal
from uuid import uuid4

import stripe
from fastapi import APIRouter, HTTPException, Request, status
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import get_database
from app.services.billing_service import sync_billing_customer_updated_event
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
PROCESSING_CLAIM_TTL_MINUTES = 15
STRIPE_WEBHOOK_MAX_BYTES = 1024 * 1024
STRIPE_WEBHOOK_RETRY_AFTER_SECONDS = 30
ClaimState = Literal["claimed", "completed", "in_progress"]


def _require_setting(value: str, name: str) -> str:
    value = (value or "").strip()
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value


async def _read_webhook_body(
    request: Request,
    *,
    max_bytes: int = STRIPE_WEBHOOK_MAX_BYTES,
) -> bytes:
    """Read a webhook body without accepting an unbounded allocation."""

    declared_length = str(request.headers.get("content-length") or "").strip()
    if declared_length:
        try:
            declared_bytes = int(declared_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header",
            ) from exc
        if declared_bytes < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header",
            )
        if declared_bytes > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Stripe webhook payload is too large",
            )

    payload = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        if len(payload) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Stripe webhook payload is too large",
            )
        payload.extend(chunk)
    return bytes(payload)


def ensure_stripe_event_indexes() -> None:
    db = get_database()
    events_col = db["stripe_events"]
    events_col.create_index(
        [("event_id", 1)],
        name="event_id_1",
        unique=True,
        sparse=True,
    )


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
) -> tuple[ClaimState, str]:
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        return "claimed", ""

    try:
        events_col.update_one(
            {"event_id": event_id},
            {"$setOnInsert": _build_event_audit_record(event, now)},
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    claim_token = str(uuid4())
    stale_before = now - timedelta(minutes=PROCESSING_CLAIM_TTL_MINUTES)
    claimed = events_col.find_one_and_update(
        {
            "event_id": event_id,
            "processed_at": {"$exists": False},
            "$or": [
                {"processing_claim": {"$exists": False}},
                {"processing_started_at": {"$lt": stale_before}},
            ],
        },
        {
            "$set": {
                "processing_claim": claim_token,
                "processing_started_at": now,
                "processing_status": "processing",
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if claimed:
        return "claimed", claim_token

    existing = events_col.find_one(
        {"event_id": event_id},
        {"processed_at": 1, "processing_claim": 1, "processing_started_at": 1},
    )
    if existing and existing.get("processed_at") is not None:
        return "completed", ""
    return "in_progress", ""


def _event_claim_update_succeeded(result: Any) -> bool:
    return int(getattr(result, "matched_count", 0) or 0) == 1


def _mark_event_processed(
    events_col: Collection[dict[str, Any]],
    *,
    event_id: str,
    claim_token: str,
    order_result: dict[str, Any],
    maintenance_result: dict[str, Any],
    billing_customer_result: dict[str, Any] | None = None,
    now: datetime,
) -> bool:
    if not event_id:
        return True

    completed_fields: dict[str, Any] = {
        "processed_at": now,
        "processing_finished_at": now,
        "processing_status": "completed",
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
    }
    if billing_customer_result is not None:
        completed_fields["billing_customer_result"] = {
            "updated": bool(billing_customer_result.get("updated")),
            "error": billing_customer_result.get("error"),
            "type": billing_customer_result.get("type"),
        }

    result = events_col.update_one(
        {
            "event_id": event_id,
            "processing_claim": claim_token,
        },
        {
            "$set": completed_fields,
            "$unset": {
                "processing_claim": "",
                "retryable_failures": "",
                "processing_failed_at": "",
            },
        },
    )
    return _event_claim_update_succeeded(result)


def _mark_event_failed(
    events_col: Collection[dict[str, Any]],
    *,
    event_id: str,
    claim_token: str,
    failures: list[str],
    order_result: dict[str, Any],
    maintenance_result: dict[str, Any],
    billing_customer_result: dict[str, Any] | None = None,
    now: datetime,
) -> bool:
    if not event_id:
        return True

    failed_fields: dict[str, Any] = {
        "processing_failed_at": now,
        "processing_finished_at": now,
        "processing_status": "retryable_failure",
        "retryable_failures": list(failures),
        "order_result": {
            "order_id": order_result.get("order_id"),
            "error": order_result.get("error"),
            "reason": order_result.get("reason"),
            "type": order_result.get("type"),
        },
        "maintenance_result": {
            "updated": bool(maintenance_result.get("updated")),
            "error": maintenance_result.get("error"),
            "type": maintenance_result.get("type"),
        },
    }
    if billing_customer_result is not None:
        failed_fields["billing_customer_result"] = {
            "updated": bool(billing_customer_result.get("updated")),
            "error": billing_customer_result.get("error"),
            "type": billing_customer_result.get("type"),
        }

    result = events_col.update_one(
        {"event_id": event_id, "processing_claim": claim_token},
        {
            "$set": failed_fields,
            "$unset": {"processing_claim": "", "processed_at": ""},
        },
    )
    return _event_claim_update_succeeded(result)


def _downstream_failures(
    *,
    event_type: str,
    order_result: dict[str, Any],
    maintenance_result: dict[str, Any],
    billing_customer_result: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    if event_type == "checkout.session.completed":
        # A checkout may represent either a package purchase or a maintenance
        # subscription. The event is complete when the relevant handler wins;
        # an expected rejection by the non-relevant handler is not a failure.
        checkout_persisted = bool(
            order_result.get("order_id")
            or order_result.get("duplicate")
            or maintenance_result.get("updated")
        )
        if not checkout_persisted:
            failures.append(
                str(
                    order_result.get("error")
                    or maintenance_result.get("error")
                    or order_result.get("reason")
                    or maintenance_result.get("reason")
                    or "checkout_not_persisted"
                )
            )
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.paid",
        "invoice.payment_failed",
    } and not maintenance_result.get("updated"):
        failures.append(
            str(
                maintenance_result.get("error")
                or maintenance_result.get("reason")
                or "maintenance_event_not_persisted"
            )
        )
    elif event_type == "customer.updated" and (
        billing_customer_result or {}
    ).get("error") == "billing_customer_sync_failed":
        failures.append("billing_customer_sync_failed")
    return list(dict.fromkeys(failure for failure in failures if failure))


def _duplicate_response(event_type: str) -> Dict[str, Any]:
    return {
        "received": True,
        "duplicate": True,
        "type": event_type,
        "order": {"order_id": None, "duplicate": True},
        "maintenance": {"updated": False, "duplicate": True},
    }


def _process_verified_event(event: dict[str, Any]) -> Dict[str, Any]:
    """Run blocking persistence and business logic outside the async event loop."""

    db = get_database()
    events_col = db["stripe_events"]

    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("type") or "unknown").strip() or "unknown"
    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe event is missing an event id",
        )

    now = datetime.now(timezone.utc)
    claim_state, claim_token = _claim_event_processing(
        events_col,
        event=event,
        now=now,
    )
    if claim_state == "completed":
        logger.info("Completed Stripe webhook duplicate delivery ignored")
        return _duplicate_response(event_type)
    if claim_state == "in_progress":
        logger.warning("Stripe webhook delivery arrived while processing is in progress")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe event processing is still in progress; retry delivery.",
            headers={"Retry-After": str(STRIPE_WEBHOOK_RETRY_AFTER_SECONDS)},
        )

    order_result: Dict[str, Any] = {"order_id": None}
    maintenance_result: Dict[str, Any] = {"updated": False}
    billing_customer_result: Dict[str, Any] = {"updated": False}

    if event_type == "checkout.session.completed":
        try:
            order_result = upsert_order_from_stripe_event(event)
        except Exception:
            logger.error("Stripe checkout order upsert failed", exc_info=True)
            order_result = {
                "order_id": None,
                "error": "order_upsert_failed",
                "type": event_type,
            }
        try:
            maintenance_result = sync_maintenance_checkout_event(event)
        except Exception:
            logger.error("Stripe checkout maintenance sync failed", exc_info=True)
            maintenance_result = {
                "updated": False,
                "error": "maintenance_checkout_sync_failed",
                "type": event_type,
            }

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        try:
            maintenance_result = sync_maintenance_subscription_event(event)
        except Exception:
            logger.error("Stripe subscription maintenance sync failed", exc_info=True)
            maintenance_result = {
                "updated": False,
                "error": "maintenance_subscription_sync_failed",
                "type": event_type,
            }

    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        try:
            maintenance_result = sync_maintenance_invoice_event(event)
        except Exception:
            logger.error("Stripe invoice maintenance sync failed", exc_info=True)
            maintenance_result = {
                "updated": False,
                "error": "maintenance_invoice_sync_failed",
                "type": event_type,
            }

    if event_type == "customer.updated":
        try:
            billing_customer_result = sync_billing_customer_updated_event(event)
        except Exception:
            logger.error("Stripe billing customer sync failed", exc_info=True)
            billing_customer_result = {
                "updated": False,
                "error": "billing_customer_sync_failed",
                "type": event_type,
            }

    failures = _downstream_failures(
        event_type=event_type,
        order_result=order_result,
        maintenance_result=maintenance_result,
        billing_customer_result=billing_customer_result,
    )
    finished_at = datetime.now(timezone.utc)
    if failures:
        released = _mark_event_failed(
            events_col,
            event_id=event_id,
            claim_token=claim_token,
            failures=failures,
            order_result=order_result,
            maintenance_result=maintenance_result,
            billing_customer_result=billing_customer_result,
            now=finished_at,
        )
        if not released:
            logger.critical("Stripe event failure could not release its owned claim")
        logger.error("Stripe webhook processing failed and is safe for retry")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe event processing failed; delivery is safe to retry.",
            headers={"Retry-After": str(STRIPE_WEBHOOK_RETRY_AFTER_SECONDS)},
        )

    committed = _mark_event_processed(
        events_col,
        event_id=event_id,
        claim_token=claim_token,
        order_result=order_result,
        maintenance_result=maintenance_result,
        billing_customer_result=billing_customer_result,
        now=finished_at,
    )
    if not committed:
        logger.critical("Stripe event completion lost claim ownership")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe event completion was not committed; retry delivery.",
            headers={"Retry-After": str(STRIPE_WEBHOOK_RETRY_AFTER_SECONDS)},
        )

    logger.info("Stripe webhook processed")
    return {
        "received": True,
        "type": event_type,
        "order": order_result,
        "maintenance": maintenance_result,
        "billing_customer": billing_customer_result,
    }


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    sig_header = str(request.headers.get("stripe-signature") or "").strip()
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    stripe.api_key = _require_setting(settings.stripe_secret_key, "stripe_secret_key")
    endpoint_secret = _require_setting(
        settings.stripe_webhook_secret,
        "stripe_webhook_secret",
    )
    payload_bytes = await _read_webhook_body(request)

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
    except Exception:
        logger.warning("Stripe webhook signature verification failed", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook")

    return await run_in_threadpool(_process_verified_event, event)
