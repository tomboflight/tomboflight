"""
Stripe Webhooks — Tomb of Light

Endpoint:
  POST /webhooks/stripe

Env vars required (Render + local .env):
  STRIPE_SECRET_KEY=sk_live_... (or sk_test_...)
  STRIPE_WEBHOOK_SECRET=whsec_...

Behavior:
- Verifies Stripe signature
- Saves the Stripe event (idempotent) into stripe_events
- Creates/updates an Order in MongoDB for:
    - checkout.session.completed
    - payment_intent.succeeded (backup)
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from app.database import get_database

# ✅ This MUST exist in app/services/order_service.py
from app.services.order_service import upsert_order_from_stripe_event

try:
    from stripe.error import SignatureVerificationError  # type: ignore
except Exception:  # pragma: no cover
    SignatureVerificationError = Exception  # type: ignore


router = APIRouter(prefix="/webhooks", tags=["Stripe Webhooks"])


def _get_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
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

    stripe.api_key = _get_env("STRIPE_SECRET_KEY")
    endpoint_secret = _get_env("STRIPE_WEBHOOK_SECRET")

    # Verify signature + parse event
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
    events_col = db.get_collection("stripe_events")

    event_id = event.get("id")
    event_type = event.get("type", "unknown")
    now = datetime.now(timezone.utc)

    # Idempotent event storage (prevents duplicates on retries/resends)
    if event_id:
        existing = events_col.find_one({"event_id": event_id})
        if not existing:
            events_col.insert_one(
                {
                    "event_id": event_id,
                    "type": event_type,
                    "livemode": bool(event.get("livemode", False)),
                    "created": event.get("created"),  # unix timestamp from Stripe
                    "received_at": now,
                    "raw": event,  # keep full event for audit/debug
                }
            )

    # === Turn Stripe events into Orders ===
    order_result: Dict[str, Any] = {}
    order_upserted = False

    if event_type in {"checkout.session.completed", "payment_intent.succeeded"}:
        try:
            order_result = upsert_order_from_stripe_event(event)
            order_upserted = True
        except Exception as e:
            # IMPORTANT: Stripe expects a 2xx ACK for valid webhooks.
            # We log failure but still ACK so Stripe doesn't keep retrying forever.
            events_col.update_one(
                {"event_id": event_id} if event_id else {"_id": None},
                {"$set": {"order_upsert_error": str(e), "order_upsert_failed_at": now}},
                upsert=bool(event_id),
            )

    return {
        "received": True,
        "type": event_type,
        "order_upserted": order_upserted,
        "order_id": order_result.get("order_id"),
        "order_meta": order_result,
    }