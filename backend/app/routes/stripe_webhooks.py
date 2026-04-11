"""
Stripe Webhooks — Tomb of Light

Endpoint:
  POST /webhooks/stripe
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, HTTPException, Request, status

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


def _require_setting(value: str, name: str) -> str:
    value = (value or "").strip()
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value


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

    event_id = event.get("id")
    event_type = event.get("type", "unknown")
    now = datetime.now(timezone.utc)

    if event_id:
        existing = events_col.find_one({"event_id": event_id})
        if not existing:
            events_col.insert_one(
                {
                    "event_id": event_id,
                    "type": event_type,
                    "livemode": bool(event.get("livemode", False)),
                    "created": event.get("created"),
                    "received_at": now,
                    "raw": event,
                }
            )

    order_result: Dict[str, Any] = {"order_id": None}
    maintenance_result: Dict[str, Any] = {"updated": False}

    # Order upsert currently maps Stripe Checkout sessions to orders.
    if event_type == "checkout.session.completed":
        try:
            order_result = upsert_order_from_stripe_event(event)
        except Exception as e:
            order_result = {"order_id": None, "error": str(e), "type": event_type}
        try:
            maintenance_result = sync_maintenance_checkout_event(event)
        except Exception as e:
            maintenance_result = {"updated": False, "error": str(e), "type": event_type}

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        try:
            maintenance_result = sync_maintenance_subscription_event(event)
        except Exception as e:
            maintenance_result = {"updated": False, "error": str(e), "type": event_type}

    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        try:
            maintenance_result = sync_maintenance_invoice_event(event)
        except Exception as e:
            maintenance_result = {"updated": False, "error": str(e), "type": event_type}

    print(
        "[stripe_webhook]",
        {
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
