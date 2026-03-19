"""
Stripe Webhooks — Tomb of Light

Endpoint:
  POST /webhooks/stripe

Env vars required (Render + local .env):
  STRIPE_SECRET_KEY=sk_live_...
  STRIPE_WEBHOOK_SECRET=whsec_...

Notes:
- This route verifies the Stripe signature and ACKs valid events.
- Next step: connect event types to your Orders system automatically.
"""

import os
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, Request, HTTPException, status

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

    # Stripe config
    # (API key not required for signature verification, but safe to set for future usage)
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
        # Invalid JSON
        raise HTTPException(status_code=400, detail="Invalid payload")
    except getattr(stripe.error, "SignatureVerificationError", Exception): # type: ignore
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    event_type = event.get("type", "unknown")

    # For now we ACK everything valid.
    # Later: route these to your Orders pipeline automatically.
    # Examples:
    # - checkout.session.completed
    # - payment_intent.succeeded
    # - charge.succeeded
    #
    return {"received": True, "type": event_type}