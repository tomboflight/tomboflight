from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse

import stripe

from app.config import settings
from app.core.package_catalog import get_addon, normalize_addon_code
from app.services.nft_addon_service import (
    ADDITIONAL_MINT_ADDON_CODE,
    INITIAL_MINT_ADDON_CODE,
    METADATA_REVISION_ADDON_CODE,
    NFT_ADDON_CODES,
    validate_nft_addon_purchase_target,
)


PRICE_SETTING_BY_ADDON = {
    INITIAL_MINT_ADDON_CODE: "stripe_nft_lineage_record_price_id",
    ADDITIONAL_MINT_ADDON_CODE: "stripe_additional_nft_mint_price_id",
    METADATA_REVISION_ADDON_CODE: "stripe_nft_metadata_revision_price_id",
}


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _stripe_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict_recursive"):
        return dict(value.to_dict_recursive())
    if isinstance(value, dict):
        return value
    return dict(value)


def _normalized_product_name(value: Any) -> str:
    normalized = _normalize(value).lower().replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^add\s*-?\s*on\s*-\s*", "", normalized)
    return normalized.strip()


def _require_stripe() -> None:
    secret = _normalize(settings.stripe_secret_key)
    if not secret:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    stripe.api_key = secret


def _expected_price(addon_code: str) -> tuple[dict[str, Any], int]:
    addon = get_addon(addon_code) or {}
    if not addon or addon_code not in NFT_ADDON_CODES:
        raise ValueError("NFT add-on is not in the approved server catalog.")
    cents = int(round(float(addon.get("price_usd") or 0) * 100))
    if cents <= 0:
        raise RuntimeError("NFT add-on price is not configured.")
    return addon, cents


def _price_matches(
    price: dict[str, Any],
    *,
    addon: dict[str, Any],
    expected_cents: int,
) -> bool:
    product = price.get("product") or {}
    if not isinstance(product, dict):
        return False
    return bool(
        _normalize(price.get("id"))
        and price.get("active") is not False
        and product.get("active") is not False
        and price.get("recurring") in (None, {})
        and _normalize(price.get("currency")).lower() == "usd"
        and price.get("unit_amount") == expected_cents
        and _normalized_product_name(product.get("name"))
        == _normalized_product_name(addon.get("display_name"))
    )


def _iter_stripe_prices(response: Any) -> Iterable[dict[str, Any]]:
    if hasattr(response, "auto_paging_iter"):
        for value in response.auto_paging_iter():
            yield _stripe_to_dict(value)
        return
    payload = _stripe_to_dict(response)
    for value in payload.get("data") or []:
        yield _stripe_to_dict(value)


def resolve_nft_addon_price_id(addon_code: str) -> str:
    code = normalize_addon_code(addon_code)
    addon, expected_cents = _expected_price(code)
    _require_stripe()

    configured_field = PRICE_SETTING_BY_ADDON[code]
    configured_price_id = _normalize(getattr(settings, configured_field, ""))
    if configured_price_id:
        price = _stripe_to_dict(
            stripe.Price.retrieve(configured_price_id, expand=["product"])
        )
        if not _price_matches(price, addon=addon, expected_cents=expected_cents):
            raise RuntimeError(
                f"Configured Stripe price for {code} does not match the approved product and USD amount."
            )
        return configured_price_id

    response = stripe.Price.list(
        active=True,
        currency="usd",
        type="one_time",
        limit=100,
        expand=["data.product"],
    )
    matches = [
        price
        for price in _iter_stripe_prices(response)
        if _price_matches(price, addon=addon, expected_cents=expected_cents)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Stripe must contain exactly one active {code} price matching the approved product and amount; found {len(matches)}. "
            f"Set {configured_field.upper()} to select the intended price."
        )
    return _normalize(matches[0].get("id"))


def _public_app_base_url() -> str:
    raw = _normalize(settings.nft_default_external_url).rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("NFT_DEFAULT_EXTERNAL_URL must be a valid public app URL.")
    if settings.is_production_environment and parsed.scheme != "https":
        raise RuntimeError("NFT_DEFAULT_EXTERNAL_URL must use HTTPS in production.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _user_id(user: dict[str, Any]) -> str:
    value = _normalize(user.get("_id") or user.get("id") or user.get("user_id"))
    if not value:
        raise ValueError("Authenticated customer id is missing.")
    return value


def _user_email(user: dict[str, Any]) -> str:
    value = _normalize(user.get("email")).lower()
    if not value or "@" not in value:
        raise ValueError("Authenticated customer email is missing.")
    return value


def create_nft_addon_checkout_session(
    *,
    user: dict[str, Any],
    project_id: str,
    addon_code: str,
) -> dict[str, Any]:
    code = normalize_addon_code(addon_code)
    validated_project = validate_nft_addon_purchase_target(
        user=user,
        project_id=project_id,
        addon_code=code,
    )
    addon, expected_cents = _expected_price(code)
    price_id = resolve_nft_addon_price_id(code)
    customer_id = _user_id(user)
    customer_email = _user_email(user)
    normalized_project_id = _normalize(validated_project.get("_id") or project_id)
    checkout_sequence = _normalize(
        validated_project.get("_nft_credit_slot")
        or validated_project.get("_nft_checkout_sequence")
        or code
    )
    reference = "tol:" + urlencode(
        {
            "v": "1",
            "u": customer_id,
            "p": normalized_project_id,
            "k": code,
            "t": "addon",
            "b": "one_time",
        }
    )
    metadata = {
        "item_type": "addon",
        "addon_code": code,
        "project_id": normalized_project_id,
        "user_id": customer_id,
        "checkout_never_triggers_mint": "true",
    }
    app_base = _public_app_base_url()
    session_params: dict[str, Any] = {
        "mode": "payment",
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": reference,
        "metadata": metadata,
        "payment_intent_data": {"metadata": metadata},
        "success_url": (
            f"{app_base}/thank-you.html?session_id={{CHECKOUT_SESSION_ID}}"
            f"&type=addon&package={code}"
        ),
        "cancel_url": f"{app_base}/dashboard.html#legacy-anchor",
        "allow_promotion_codes": False,
        "billing_address_collection": "auto",
        "idempotency_key": "tol-nft-checkout-"
        + hashlib.sha256(
            f"{customer_id}:{normalized_project_id}:{code}:{checkout_sequence}".encode(
                "utf-8"
            )
        ).hexdigest(),
    }
    stripe_customer_id = _normalize(user.get("stripe_customer_id"))
    if stripe_customer_id.startswith("cus_"):
        session_params["customer"] = stripe_customer_id
    else:
        session_params["customer_email"] = customer_email
        session_params["customer_creation"] = "always"

    _require_stripe()
    session = _stripe_to_dict(stripe.checkout.Session.create(**session_params))
    checkout_url = _normalize(session.get("url"))
    parsed_checkout = urlparse(checkout_url)
    if parsed_checkout.scheme != "https" or parsed_checkout.netloc != "checkout.stripe.com":
        raise RuntimeError("Stripe did not return a valid hosted Checkout URL.")
    return {
        "session_id": _normalize(session.get("id")),
        "checkout_url": checkout_url,
        "project_id": normalized_project_id,
        "addon_code": code,
        "amount_cents": expected_cents,
        "currency": "usd",
        "checkout_creates_credit_only": True,
        "checkout_never_triggers_mint": True,
        "expires_at": session.get("expires_at"),
    }
