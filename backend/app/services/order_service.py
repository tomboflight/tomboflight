from datetime import UTC, datetime
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

from app.database import get_database


def _get_orders_collection() -> Collection:
    db = cast(Database, get_database())
    return db.get_collection("orders")


def _serialize_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(order["_id"]),
        "user_id": str(order["user_id"]),
        "email": order["email"],
        "package_slug": order["package_slug"],
        "package_name": order["package_name"],
        "price_label": order["price_label"],
        "source": order.get("source", "stripe_payment_link"),
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

    docs = list(
        orders.find({"user_id": ObjectId(user["_id"])}).sort("created_at", -1)
    )

    return [_serialize_order(doc) for doc in docs]


def ensure_order_indexes() -> None:
    orders = _get_orders_collection()
    orders.create_index("user_id")
    orders.create_index("email")
    orders.create_index("package_slug")
    orders.create_index("created_at")