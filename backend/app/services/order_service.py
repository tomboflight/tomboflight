from datetime import UTC, datetime
from typing import Any, Optional, cast

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
            "user_id": ObjectId(user["_id"]),
            "package_slug": payload.package_slug,
            "status": payload.order_status,
        },
        sort=[("created_at", -1)],
    )

    if existing:
        return _serialize_order(existing)

    order_doc = {
        "user_id": ObjectId(user["_id"]),
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
    docs = list(orders.find({"user_id": ObjectId(user["_id"])}).sort("created_at", -1))
    return [_serialize_order(doc) for doc in docs]


# ----------------------------
# Indexes (safe + non-crashing)
# ----------------------------
def ensure_order_indexes() -> None:
    """
    Create indexes safely with explicit names and avoid index-name conflicts.

    Your DB already has:
      stripe_session_id_1 (unique + sparse)

    If an index already exists, we skip it rather than crashing the app.
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
        # If the index name already exists, do not attempt to recreate it.
        if name in existing:
            return

        try:
            orders.create_index(keys, name=name, unique=unique, sparse=sparse)
        except OperationFailure:
            # If something else created it between reads, ignore.
            return

    _ensure_index([("user_id", 1)], name="user_id_1")
    _ensure_index([("email", 1)], name="email_1")
    _ensure_index([("package_slug", 1)], name="package_slug_1")
    _ensure_index([("created_at", -1)], name="created_at_-1")

    # Webhook idempotency / Stripe linkage
    # Match the DB's existing index behavior: UNIQUE + SPARSE
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


# ----------------------------
# Stripe -> Order upsert
# ----------------------------
def _get_email_from_event(event: dict[str, Any]) -> Optional[str]:
    data = (event.get("data") or {}).get("object") or {}

    # checkout.session.completed
    customer_details = data.get("customer_details") or {}
    email = customer_details.get("email")

    # fallback: customer_email sometimes exists on session
    if not email:
        email = data.get("customer_email")

    # payment_intent.succeeded fallback (rare)
    if not email:
        charges = (((data.get("charges") or {}).get("data")) or [])
        if charges:
            billing = charges[0].get("billing_details") or {}
            email = billing.get("email")

    return email


def _get_package_fields_from_event(event: dict[str, Any]) -> tuple[str, str, str]:
    """
    Returns: (package_slug, package_name, price_label)
    We expect you to put these in Stripe metadata later.
    For now, safe fallbacks.
    """
    data = (event.get("data") or {}).get("object") or {}
    metadata = data.get("metadata") or {}

    package_slug = metadata.get("package_slug") or metadata.get("package") or "unknown"
    package_name = metadata.get("package_name") or "Tomb of Light Package"
    price_label = metadata.get("price_label") or "paid"

    return package_slug, package_name, price_label


def upsert_order_from_stripe_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Creates an Order IF we can match Stripe's email to an existing user record.
    Idempotent by stripe_session_id for checkout.session.completed.

    Returns:
      {"order_id": "...", ...} or {"order_id": None, "reason": "..."}
    """
    event_type = event.get("type", "")
    data = (event.get("data") or {}).get("object") or {}

    email = _get_email_from_event(event)
    if not email:
        return {"order_id": None, "reason": "no_email_in_event", "type": event_type}

    users = _get_users_collection()
    user = users.find_one({"email": email})
    if not user:
        return {
            "order_id": None,
            "reason": "no_matching_user",
            "email": email,
            "type": event_type,
        }

    orders = _get_orders_collection()

    stripe_session_id: Optional[str] = None
    stripe_payment_link_id: Optional[str] = None

    if event_type == "checkout.session.completed":
        stripe_session_id = data.get("id")
        stripe_payment_link_id = data.get("payment_link")
    elif event_type == "payment_intent.succeeded":
        # backup event; may not map cleanly to a session
        stripe_session_id = data.get("id")
        stripe_payment_link_id = data.get("payment_link")

    if not stripe_session_id:
        return {"order_id": None, "reason": "no_session_id", "email": email, "type": event_type}

    existing = orders.find_one({"stripe_session_id": stripe_session_id})
    if existing:
        return {"order_id": str(existing["_id"]), "existing": True, "type": event_type}

    package_slug, package_name, price_label = _get_package_fields_from_event(event)

    order_doc = {
        "user_id": ObjectId(user["_id"]),
        "email": email,
        "package_slug": package_slug,
        "package_name": package_name,
        "price_label": price_label,
        "source": "stripe_webhook",
        "status": "paid",
        "stripe_session_id": stripe_session_id,
        "stripe_payment_link_id": stripe_payment_link_id,
        "created_at": datetime.now(UTC),
    }

    result = orders.insert_one(order_doc)
    return {"order_id": str(result.inserted_id), "existing": False, "type": event_type}