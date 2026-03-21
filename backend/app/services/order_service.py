import re
from datetime import UTC, datetime
from typing import Any, Optional, cast

import stripe
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.database import get_database


def _get_orders_collection() -> Collection:
    db = cast(Database, get_database())
    return db.get_collection("orders")


def _get_users_collection() -> Collection:
    db = cast(Database, get_database())
    return db.get_collection("users")


def _serialize_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(order["_id"]),
        "user_id": str(order["user_id"]),
        "email": order["email"],
        "package_slug": order.get("package_slug", ""),
        "package_name": order.get("package_name", ""),
        "price_label": order.get("price_label", ""),
        "source": order.get("source", "stripe"),
        "status": order.get("status", "paid"),
        "stripe_session_id": order.get("stripe_session_id"),
        "stripe_payment_link_id": order.get("stripe_payment_link_id"),
        "created_at": order["created_at"],
    }


def create_order_for_user(user: dict[str, Any], payload: Any) -> dict[str, Any]:
    orders = _get_orders_collection()

    existing = orders.find_one(
        {
            "user_id": ObjectId(str(user["_id"])),
            "package_slug": payload.package_slug,
            "status": payload.order_status,
        },
        sort=[("created_at", -1)],
    )

    if existing:
        return _serialize_order(existing)

    order_doc = {
        "user_id": ObjectId(str(user["_id"])),
        "email": user["email"],
        "package_slug": payload.package_slug,
        "package_name": payload.package_name,
        "price_label": payload.price_label,
        "source": payload.source,
        "status": payload.order_status,
        "stripe_session_id": payload.stripe_session_id,
        "stripe_payment_link_id": payload.stripe_payment_link_id,
        "created_at": datetime.now(UTC),
    }

    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id
    return _serialize_order(order_doc)


def get_orders_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    orders = _get_orders_collection()
    docs = list(
        orders.find({"user_id": ObjectId(str(user["_id"]))}).sort("created_at", -1)
    )
    return [_serialize_order(doc) for doc in docs]


def ensure_order_indexes() -> None:
    """
    Create indexes safely with explicit names and avoid index-name conflicts.
    """
    orders = _get_orders_collection()
    existing = orders.index_information()

    def _ensure_index(
        keys: list[tuple[str, int]],
        *,
        name: str,
        unique: bool = False,
        sparse: bool = False,
    ) -> None:
        if name in existing:
            return

        try:
            orders.create_index(keys, name=name, unique=unique, sparse=sparse)
        except OperationFailure:
            return

    _ensure_index([("user_id", 1)], name="user_id_1")
    _ensure_index([("email", 1)], name="email_1")
    _ensure_index([("package_slug", 1)], name="package_slug_1")
    _ensure_index([("created_at", -1)], name="created_at_-1")
    _ensure_index(
        [("stripe_session_id", 1)],
        name="stripe_session_id_1",
        unique=True,
        sparse=True,
    )
    _ensure_index(
        [("stripe_payment_link_id", 1)],
        name="stripe_payment_link_id_1",
        unique=False,
        sparse=True,
    )


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def _get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    users = _get_users_collection()

    exact = users.find_one({"email": email})
    if exact:
        return exact

    return users.find_one(
        {
            "email": {
                "$regex": f"^{re.escape(email)}$",
                "$options": "i",
            }
        }
    )


def _event_object(event: dict[str, Any]) -> dict[str, Any]:
    return ((event.get("data") or {}).get("object") or {}) if isinstance(event, dict) else {}


def _retrieve_checkout_session(session_id: str) -> dict[str, Any]:
    session = stripe.checkout.Session.retrieve(
        session_id,
        expand=["line_items.data.price.product"],
    )

    if hasattr(session, "to_dict_recursive"):
        return session.to_dict_recursive()

    return dict(session)


def _extract_email_from_session(session: dict[str, Any]) -> Optional[str]:
    customer_details = session.get("customer_details") or {}
    email = customer_details.get("email")

    if not email:
        email = session.get("customer_email")

    return _normalize_email(email)


def _extract_product_name_from_session(session: dict[str, Any]) -> Optional[str]:
    line_items = ((session.get("line_items") or {}).get("data")) or []
    if not line_items:
        return None

    first_item = line_items[0] or {}

    description = first_item.get("description")
    if description:
        return str(description).strip()

    price_obj = first_item.get("price") or {}
    product_obj = price_obj.get("product") or {}

    product_name = product_obj.get("name")
    if product_name:
        return str(product_name).strip()

    return None


def _infer_package_fields(session: dict[str, Any]) -> tuple[str, str, str]:
    metadata = session.get("metadata") or {}

    package_slug = metadata.get("package_slug") or metadata.get("package")
    package_name = metadata.get("package_name")
    price_label = metadata.get("price_label")

    if package_slug and package_name and price_label:
        return str(package_slug), str(package_name), str(price_label)

    product_name = _extract_product_name_from_session(session)
    amount_subtotal = session.get("amount_subtotal")

    if isinstance(product_name, str):
        name_lower = product_name.lower()

        if "legacy plus" in name_lower:
            return "legacy-plus", "Legacy Plus", "$3,200"
        if "heirloom" in name_lower:
            return "heirloom-legacy-tree", "Heirloom Legacy Tree", "$1,500"
        if "starter" in name_lower:
            return "starter-family-tree", "Starter Family Tree", "$799"
        if "portrait" in name_lower:
            return "digital-legacy-portrait", "Digital Legacy Portrait", "$399"

    if amount_subtotal == 320000:
        return "legacy-plus", "Legacy Plus", "$3,200"
    if amount_subtotal == 150000:
        return "heirloom-legacy-tree", "Heirloom Legacy Tree", "$1,500"
    if amount_subtotal == 79900:
        return "starter-family-tree", "Starter Family Tree", "$799"
    if amount_subtotal == 39900:
        return "digital-legacy-portrait", "Digital Legacy Portrait", "$399"

    return "unknown", "Tomb of Light Package", "paid"


def _get_email_from_event(event: dict[str, Any]) -> Optional[str]:
    data = _event_object(event)

    customer_details = data.get("customer_details") or {}
    email = customer_details.get("email")

    if not email:
        email = data.get("customer_email")

    if not email:
        charges = (((data.get("charges") or {}).get("data")) or [])
        if charges:
            billing = charges[0].get("billing_details") or {}
            email = billing.get("email")

    return _normalize_email(email)


def upsert_order_from_stripe_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Creates an Order IF we can match Stripe's email to an existing user record.
    Uses checkout.session.completed as the primary order creation event.

    Returns:
      {"order_id": "...", ...} or {"order_id": None, "reason": "..."}
    """
    event_type = event.get("type", "")
    data = _event_object(event)

    if event_type != "checkout.session.completed":
        return {
            "order_id": None,
            "ignored": True,
            "reason": "event_type_not_used_for_order_creation",
            "type": event_type,
        }

    session_id = data.get("id")
    if not session_id:
        return {"order_id": None, "reason": "no_session_id", "type": event_type}

    try:
        session = _retrieve_checkout_session(session_id)
    except Exception as e:
        return {
            "order_id": None,
            "reason": "session_retrieve_failed",
            "type": event_type,
            "session_id": session_id,
            "error": str(e),
        }

    email = _extract_email_from_session(session)
    if not email:
        email = _get_email_from_event(event)

    if not email:
        return {
            "order_id": None,
            "reason": "no_email_in_checkout_session",
            "type": event_type,
            "session_id": session_id,
        }

    user = _get_user_by_email(email)
    if not user:
        return {
            "order_id": None,
            "reason": "no_matching_user",
            "type": event_type,
            "session_id": session_id,
            "email": email,
        }

    orders = _get_orders_collection()

    existing = orders.find_one({"stripe_session_id": session_id})
    if existing:
        return {
            "order_id": str(existing["_id"]),
            "existing": True,
            "type": event_type,
            "session_id": session_id,
        }

    package_slug, package_name, price_label = _infer_package_fields(session)

    order_doc = {
        "user_id": ObjectId(str(user["_id"])),
        "email": email,
        "package_slug": package_slug,
        "package_name": package_name,
        "price_label": price_label,
        "source": "stripe_webhook",
        "status": "paid",
        "stripe_session_id": session_id,
        "stripe_payment_link_id": session.get("payment_link"),
        "created_at": datetime.now(UTC),
    }

    result = orders.insert_one(order_doc)

    return {
        "order_id": str(result.inserted_id),
        "existing": False,
        "type": event_type,
        "session_id": session_id,
        "email": email,
        "package_slug": package_slug,
    }