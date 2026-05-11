from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse

import stripe
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings
from app.database import get_database
from app.services.audit_log_service import create_audit_log


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _db() -> Database:
    db = cast(Database | None, get_database())
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db


def _users_collection() -> Collection:
    return _db().get_collection("users")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _current_user_id(user: dict[str, Any]) -> str:
    raw_value = user.get("_id") or user.get("id") or user.get("user_id")
    return _normalize_text(raw_value)


def _current_user_email(user: dict[str, Any]) -> str:
    return _normalize_text(user.get("email")).lower()


def _current_user_name(user: dict[str, Any]) -> str:
    return _normalize_text(
        user.get("full_name") or user.get("name") or user.get("display_name")
    )


def _require_stripe_secret_key() -> str:
    secret_key = _normalize_text(settings.stripe_secret_key)
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    stripe.api_key = secret_key
    return secret_key


def _validate_portal_return_url(return_url: str | None) -> str:
    normalized = _normalize_text(return_url)
    fallback = (
        settings.stripe_billing_portal_return_url_clean
        or "https://tomboflight.com/billing.html"
    )
    if not normalized:
        return fallback

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return fallback

    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in set(settings.allowed_origins_list):
        return fallback

    return normalized


def _stripe_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict_recursive"):
        return cast(dict[str, Any], value.to_dict_recursive())
    if isinstance(value, dict):
        return value
    return cast(dict[str, Any], dict(value))


def _user_lookup_query(user_id: str) -> dict[str, Any]:
    try:
        return {"_id": ObjectId(user_id)}
    except Exception:
        return {"_id": user_id}


def _get_user_document(user: dict[str, Any]) -> dict[str, Any]:
    user_id = _current_user_id(user)
    if not user_id:
        raise ValueError("Authenticated user id is missing.")

    document = _users_collection().find_one(_user_lookup_query(user_id))
    if document is None:
        raise ValueError("User account not found.")
    return document


def _save_customer_id_to_user(user_id: str, customer_id: str) -> None:
    _users_collection().update_one(
        _user_lookup_query(user_id),
        {
            "$set": {
                "stripe_customer_id": _normalize_text(customer_id),
                "stripe_customer_updated_at": _now_iso(),
            }
        },
    )


def _existing_customer_id_for_user(user: dict[str, Any]) -> str:
    document = _get_user_document(user)
    return _normalize_text(document.get("stripe_customer_id"))


def store_stripe_customer_reference(
    *,
    user_id: str | None = None,
    email: str | None = None,
    customer_id: str,
) -> None:
    normalized_customer_id = _normalize_text(customer_id)
    if not normalized_customer_id:
        return

    users = _users_collection()
    if user_id:
        users.update_one(
            _user_lookup_query(user_id),
            {
                "$set": {
                    "stripe_customer_id": normalized_customer_id,
                    "stripe_customer_updated_at": _now_iso(),
                }
            },
        )
        return

    normalized_email = _normalize_text(email).lower()
    if normalized_email:
        users.update_one(
            {"email": normalized_email},
            {
                "$set": {
                    "stripe_customer_id": normalized_customer_id,
                    "stripe_customer_updated_at": _now_iso(),
                }
            },
        )


def _ensure_stripe_customer_for_user(user: dict[str, Any]) -> dict[str, Any]:
    _require_stripe_secret_key()
    document = _get_user_document(user)
    user_id = _current_user_id(document)
    email = _current_user_email(document)
    full_name = _current_user_name(document)

    existing_customer_id = _normalize_text(document.get("stripe_customer_id"))
    if existing_customer_id:
        try:
            existing_customer = stripe.Customer.retrieve(existing_customer_id)
            customer_dict = _stripe_to_dict(existing_customer)
            if not bool(customer_dict.get("deleted")):
                return customer_dict
        except Exception:
            pass

    create_payload: dict[str, Any] = {
        "metadata": {
            "user_id": user_id,
            "platform": "tomboflight",
        },
    }
    if email:
        create_payload["email"] = email
    if full_name:
        create_payload["name"] = full_name

    created_customer = stripe.Customer.create(**create_payload)
    customer_dict = _stripe_to_dict(created_customer)
    customer_id = _normalize_text(customer_dict.get("id"))
    if customer_id:
        _save_customer_id_to_user(user_id, customer_id)

    return customer_dict


def _customer_id_for_user(user: dict[str, Any]) -> str:
    customer = _ensure_stripe_customer_for_user(user)
    customer_id = _normalize_text(customer.get("id"))
    if not customer_id:
        raise RuntimeError("Stripe customer could not be resolved.")
    return customer_id


def _list_payment_methods(customer_id: str) -> list[dict[str, Any]]:
    _require_stripe_secret_key()
    result = stripe.PaymentMethod.list(
        customer=customer_id,
        type="card",
        limit=10,
    )
    payload = _stripe_to_dict(result)
    items = payload.get("data") or []
    return [cast(dict[str, Any], _stripe_to_dict(item)) for item in items]


def _default_payment_method_id(customer: dict[str, Any]) -> str | None:
    invoice_settings = customer.get("invoice_settings") or {}
    default_payment_method = invoice_settings.get("default_payment_method")
    if isinstance(default_payment_method, dict):
        return _normalize_text(default_payment_method.get("id")) or None
    return _normalize_text(default_payment_method) or None


def _serialize_card_created(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), UTC).isoformat()
    except Exception:
        return _normalize_text(value) or None


def get_billing_overview(user: dict[str, Any]) -> dict[str, Any]:
    _require_stripe_secret_key()
    customer_id = _existing_customer_id_for_user(user)
    if not customer_id:
        return {
            "customer_id": None,
            "error_code": "billing_profile_missing",
            "message": "Your billing profile is not connected yet. Contact support@tomboflight.com for help.",
            "max_cards": max(1, int(settings.stripe_payment_method_max_cards or 3)),
            "cards_on_file": 0,
            "can_add_card": False,
            "default_payment_method_id": None,
            "payment_methods": [],
            "subscriptions": [],
        }

    customer = stripe.Customer.retrieve(customer_id)
    customer_dict = _stripe_to_dict(customer)
    if bool(customer_dict.get("deleted")):
        return {
            "customer_id": None,
            "error_code": "billing_profile_missing",
            "message": "Your billing profile is not connected yet. Contact support@tomboflight.com for help.",
            "max_cards": max(1, int(settings.stripe_payment_method_max_cards or 3)),
            "cards_on_file": 0,
            "can_add_card": False,
            "default_payment_method_id": None,
            "payment_methods": [],
            "subscriptions": [],
        }

    default_payment_method_id = _default_payment_method_id(customer)
    payment_methods = _list_payment_methods(customer_id)

    for item in payment_methods:
        item["created"] = _serialize_card_created(item.get("created"))

    subscriptions_result = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=10,
        expand=["data.default_payment_method", "data.items.data.price.product"],
    )
    subscriptions_payload = _stripe_to_dict(subscriptions_result)
    subscriptions = subscriptions_payload.get("data") or []

    max_cards = max(1, int(settings.stripe_payment_method_max_cards or 3))

    return {
        "customer_id": customer_id or None,
        "error_code": None,
        "message": None,
        "max_cards": max_cards,
        "cards_on_file": len(payment_methods),
        "can_add_card": len(payment_methods) < max_cards,
        "default_payment_method_id": default_payment_method_id,
        "payment_methods": payment_methods,
        "subscriptions": [
            cast(dict[str, Any], _stripe_to_dict(item)) for item in subscriptions
        ],
    }


def get_billing_config() -> dict[str, Any]:
    return {
        "publishable_key": _normalize_text(settings.stripe_publishable_key),
        "max_cards": max(1, int(settings.stripe_payment_method_max_cards or 3)),
        "portal_return_url": settings.stripe_billing_portal_return_url_clean or None,
    }


def create_setup_intent_for_user(user: dict[str, Any]) -> dict[str, Any]:
    _require_stripe_secret_key()
    overview = get_billing_overview(user)
    max_cards = max(1, int(settings.stripe_payment_method_max_cards or 3))
    if int(overview.get("cards_on_file") or 0) >= max_cards:
        raise ValueError(f"You can store up to {max_cards} cards on file.")

    customer_id = _normalize_text(overview.get("customer_id"))
    if not customer_id:
        raise RuntimeError("Stripe customer could not be resolved.")

    setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        usage="off_session",
        payment_method_types=["card"],
        metadata={
            "platform": "tomboflight",
            "user_id": _current_user_id(user),
        },
    )
    payload = _stripe_to_dict(setup_intent)
    client_secret = _normalize_text(payload.get("client_secret"))
    if not client_secret:
        raise RuntimeError("Stripe setup intent did not return a client secret.")

    try:
        create_audit_log(
            "billing_setup_intent_created",
            _current_user_id(user) or None,
            "stripe_customer",
            customer_id,
            {"max_cards": max_cards},
        )
    except Exception:
        pass

    return {
        "client_secret": client_secret,
        "customer_id": customer_id,
        "max_cards": max_cards,
    }


def _ensure_payment_method_belongs_to_customer(
    customer_id: str,
    payment_method_id: str,
) -> dict[str, Any]:
    _require_stripe_secret_key()
    payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
    payload = _stripe_to_dict(payment_method)
    owner = payload.get("customer")
    if isinstance(owner, dict):
        owner_id = _normalize_text(owner.get("id"))
    else:
        owner_id = _normalize_text(owner)

    if owner_id != _normalize_text(customer_id):
        raise ValueError("Payment method does not belong to this customer.")

    return payload


def set_default_payment_method_for_user(
    user: dict[str, Any],
    payment_method_id: str,
) -> dict[str, Any]:
    customer_id = _customer_id_for_user(user)
    normalized_payment_method_id = _normalize_text(payment_method_id)
    if not normalized_payment_method_id:
        raise ValueError("Payment method id is required.")

    _ensure_payment_method_belongs_to_customer(customer_id, normalized_payment_method_id)
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": normalized_payment_method_id},
    )

    try:
        create_audit_log(
            "billing_default_payment_method_set",
            _current_user_id(user) or None,
            "stripe_customer",
            customer_id,
            {"payment_method_id": normalized_payment_method_id},
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": "Default payment method updated successfully.",
        "payment_method_id": normalized_payment_method_id,
    }


def detach_payment_method_for_user(
    user: dict[str, Any],
    payment_method_id: str,
) -> dict[str, Any]:
    customer = _ensure_stripe_customer_for_user(user)
    customer_id = _normalize_text(customer.get("id"))
    normalized_payment_method_id = _normalize_text(payment_method_id)
    if not normalized_payment_method_id:
        raise ValueError("Payment method id is required.")

    _ensure_payment_method_belongs_to_customer(customer_id, normalized_payment_method_id)

    payment_methods = _list_payment_methods(customer_id)
    default_payment_method_id = _default_payment_method_id(customer)

    replacement_default_id = ""
    if normalized_payment_method_id == default_payment_method_id:
        for item in payment_methods:
            candidate_id = _normalize_text((item or {}).get("id"))
            if candidate_id and candidate_id != normalized_payment_method_id:
                replacement_default_id = candidate_id
                break

    stripe.PaymentMethod.detach(normalized_payment_method_id)
    stripe.Customer.modify(
        customer_id,
        invoice_settings={
            "default_payment_method": replacement_default_id or "",
        },
    )

    try:
        create_audit_log(
            "billing_payment_method_detached",
            _current_user_id(user) or None,
            "stripe_customer",
            customer_id,
            {"payment_method_id": normalized_payment_method_id},
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": "Payment method removed successfully.",
        "payment_method_id": normalized_payment_method_id,
    }


def create_billing_portal_session_for_user(
    user: dict[str, Any],
    *,
    return_url: str | None = None,
) -> dict[str, Any]:
    configuration_id = _normalize_text(settings.stripe_billing_portal_configuration_id)
    if not configuration_id:
        raise ValueError(
            "stripe_portal_not_configured: Billing portal is not configured yet. Please contact support@tomboflight.com."
        )
    _require_stripe_secret_key()

    customer_id = _existing_customer_id_for_user(user)
    if not customer_id:
        raise ValueError(
            "billing_profile_missing: Your billing profile is not connected yet. Contact support@tomboflight.com for help."
        )

    resolved_return_url = _validate_portal_return_url(return_url)

    kwargs: dict[str, Any] = {
        "customer": customer_id,
        "return_url": resolved_return_url,
    }

    kwargs["configuration"] = configuration_id

    session = stripe.billing_portal.Session.create(**kwargs)
    payload = _stripe_to_dict(session)
    url = _normalize_text(payload.get("url"))
    if not url:
        raise RuntimeError("Stripe billing portal did not return a URL.")

    try:
        create_audit_log(
            "billing_portal_session_created",
            _current_user_id(user) or None,
            "stripe_customer",
            customer_id,
            {},
        )
    except Exception:
        pass

    return {"url": url}
