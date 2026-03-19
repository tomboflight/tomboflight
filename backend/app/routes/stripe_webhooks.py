"""
Stripe Webhooks — Tomb of Light

Endpoint:
  POST /webhooks/stripe

Env vars required (Render + local .env):
  STRIPE_SECRET_KEY=sk_live_... (or sk_test_...)
  STRIPE_WEBHOOK_SECRET=whsec_...

Notes:
- Verifies Stripe signature.
- ACKs valid events.
- Next step: connect checkout.session.completed to your Orders pipeline.
"""

import os
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, HTTPException, Request, status

try:
    # Preferred import (helps editors/type-checkers)
    from stripe.error import SignatureVerificationError # type: ignore
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

    # Stripe config (API key not needed just to verify signature, but we set it for later usage)
    stripe.api_key = _get_env("STRIPE_SECRET_KEY")
    endpoint_secret = _get_env("STRIPE_WEBHOOK_SECRET")

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

    event_type = event.get("type", "unknown")

    # For now: ACK everything valid
    return {"received": True, "type": event_type}