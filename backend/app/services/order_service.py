import re
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional, cast
from urllib.parse import parse_qsl

import stripe
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.config import settings
from app.core.package_catalog import get_addon, get_addon_catalog, get_package, normalize_addon_code
from app.core.package_mapping import normalize_package_code as normalize_mapped_package_code
from app.database import get_database
from app.services.auth_service import create_pending_checkout_user
from app.services.billing_service import store_stripe_customer_reference
from app.services.project_service import (
    apply_package_purchase_to_project,
    create_project_from_paid_order,
)
from app.services.project_entitlement_service import (
    get_project_entitlement,
    update_project_entitlement_maintenance,
)
from app.services.project_entitlement_service import MAINTENANCE_START_DELAY_DAYS
from app.services.nft_addon_service import (
    NFT_ADDON_CODES,
    validate_nft_addon_purchase_target,
)
from app.services.paid_addon_service import validate_paid_addon_purchase_target

AUTHORITATIVE_ORDER_SOURCES = {
    "stripe_webhook",
    "stripe_verified",
    "admin_manual",
}

PAID_ORDER_STATUSES = {"paid", "complete", "completed", "succeeded"}
PENDING_PUBLIC_ORDER_STATUS = "pending_confirmation"
FULFILLMENT_PENDING = "pending_manual_fulfillment"
FULFILLMENT_IN_PROGRESS = "fulfillment_in_progress"
FULFILLMENT_COMPLETE = "fulfillment_complete"
FULFILLMENT_ESCALATED = "payment_mismatch_escalated"
FULFILLMENT_AUTO = "auto_provisioned"
OPEN_FULFILLMENT_STATUSES = {FULFILLMENT_PENDING, FULFILLMENT_IN_PROGRESS, FULFILLMENT_ESCALATED}


def manual_fulfillment_mode_enabled() -> bool:
    return bool(getattr(settings, "manual_fulfillment_mode", True))
logger = logging.getLogger(__name__)


def _get_orders_collection() -> Collection:
    db = cast(Database, get_database())
    return db.get_collection("orders")


def _get_users_collection() -> Collection:
    db = cast(Database, get_database())
    return db.get_collection("users")


def _normalize(value: Optional[str]) -> str:
    return str(value or "").strip()


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def _normalize_package_code(value: Optional[str]) -> str:
    normalized = normalize_mapped_package_code(value)
    return normalized or "unknown"


def _package_lane_for_code(package_code: str) -> str:
    package = get_package(_normalize_package_code(package_code)) or {}
    lane = _normalize(str(package.get("package_lane") or "")).lower()
    return lane or "unknown"


def _normalize_status(value: Any) -> str:
    return _normalize(str(value or "")).lower()


def _is_authoritative_order_source(source: Any) -> bool:
    return _normalize_status(source) in AUTHORITATIVE_ORDER_SOURCES


def _public_checkout_status(source: Any, requested_status: Any) -> str:
    status_value = _normalize_status(requested_status) or "pending_confirmation"
    if _is_authoritative_order_source(source):
        return status_value
    if status_value in {"paid", "complete", "completed", "succeeded"}:
        return "pending_confirmation"
    return status_value


def _set_if_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None and _normalize(str(value)):
        target[key] = value


def _trigger_package_provisioning() -> None:
    try:
        from app.services.package_provisioning_service import (
            provision_after_order_change,
        )

        provision_after_order_change(limit=25)
    except Exception as exc:
        logger.warning("package_provisioning_order_reconcile_failed", exc_info=exc)


def _coerce_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value

    normalized = _normalize(str(value or ""))
    if ObjectId.is_valid(normalized):
        return ObjectId(normalized)

    return None


def _to_object_id(value: Any) -> ObjectId | None:
    return _coerce_object_id(value)


APPROVED_PROJECT_PHASES = {
    "intake_approved",
    "build_started",
    "quality_review",
    "client_review",
    "delivery_complete",
    "delivered",
    "archived",
}
APPROVED_PROJECT_STATUSES = {
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
}


def _project_is_approved(project: dict[str, Any]) -> bool:
    status_value = _normalize(project.get("status")).lower()
    phase_value = _normalize(project.get("phase")).lower()
    return (
        status_value in APPROVED_PROJECT_STATUSES
        or phase_value in APPROVED_PROJECT_PHASES
    )


def _find_matching_approved_project(
    *,
    user: dict[str, Any],
    email: str | None = None,
) -> Optional[dict[str, Any]]:
    db = cast(Database, get_database())
    projects = db.get_collection("projects")

    owner_email = _normalize_email(email or str(user.get("email") or ""))
    user_id_text = _normalize(
        str(user.get("_id") or user.get("id") or user.get("user_id") or "")
    )
    user_oid = _coerce_object_id(user_id_text)

    filters: list[dict[str, Any]] = []
    if owner_email:
        filters.append({"owner_email": owner_email})
    if user_id_text:
        filters.append({"owner_user_id": user_id_text})
    if user_oid is not None:
        filters.append({"owner_user_id": str(user_oid)})

    if not filters:
        return None

    cursor = projects.find({"$or": filters}).sort("updated_at", -1).limit(100)
    for project in cursor:
        if _project_is_approved(project):
            return cast(dict[str, Any], project)
    return None


def _user_for_order(order_doc: dict[str, Any]) -> dict[str, Any] | None:
    users = _get_users_collection()
    user_id = _coerce_object_id(order_doc.get("user_id"))
    if user_id:
        user = users.find_one({"_id": user_id})
        if user:
            return user

    email = _normalize_email(order_doc.get("email"))
    if not email:
        return None

    return _get_user_by_email(email) or create_pending_checkout_user(email)


def _find_existing_project_for_paid_order(
    *,
    db: Database,
    order_doc: dict[str, Any],
    user: dict[str, Any],
    package_code: str,
) -> dict[str, Any] | None:
    owner_values = {
        _normalize(str(user.get("_id") or user.get("id") or user.get("user_id") or "")),
        _normalize(str(order_doc.get("user_id") or "")),
    }
    owner_emails = {
        _normalize_email(user.get("email")) or "",
        _normalize_email(order_doc.get("email")) or "",
    }
    package_values = {
        package_code,
        _normalize(str(order_doc.get("package_code") or "")),
        _normalize(str(order_doc.get("package_slug") or "")),
        _normalize(str(order_doc.get("package_type") or "")),
    }

    owner_filters: list[dict[str, Any]] = []
    for owner_value in owner_values:
        if owner_value:
            owner_filters.append({"owner_user_id": owner_value})
    for owner_email in owner_emails:
        if owner_email:
            owner_filters.append({"owner_email": owner_email})

    package_filters: list[dict[str, Any]] = []
    for package_value in package_values:
        if package_value:
            package_filters.extend(
                [
                    {"package_code": package_value},
                    {"package_slug": package_value},
                    {"package_type": package_value},
                ]
            )

    if not owner_filters or not package_filters:
        return None

    return db.projects.find_one(
        {"$and": [{"$or": owner_filters}, {"$or": package_filters}]},
        sort=[("created_at", -1)],
    )


def _link_order_to_project(
    *,
    orders: Collection,
    order_id: ObjectId,
    order_doc: dict[str, Any],
    project: dict[str, Any] | None,
) -> None:
    if not project:
        return
    project_oid = _coerce_object_id(project.get("_id") or project.get("id"))
    if project_oid is None:
        return
    project_package_code = _normalize_package_code(
        project.get("package_code") or project.get("package_slug") or order_doc.get("package_code")
    )
    raw_project_lane = _normalize(str(project.get("project_lane") or project.get("lane") or "")).lower()
    project_lane = raw_project_lane or _package_lane_for_code(project_package_code)
    orders.update_one(
        {"_id": order_id},
        {
            "$set": {
                "project_id": project_oid,
                "package_code": project_package_code,
                "package_slug": project_package_code,
                "lane": project_lane,
                "package_lane": project_lane,
            }
        },
    )
    order_doc["project_id"] = project_oid


def _attach_project_to_paid_package_order(
    *,
    order_id: ObjectId,
    order_doc: dict[str, Any],
    user: dict[str, Any],
    package_code: str,
    package_name: str,
    target_project_id: str = "",
    stripe_session_id: str | None = None,
    stripe_payment_link_id: str | None = None,
) -> dict[str, Any]:
    if _normalize_status(order_doc.get("item_type") or "package") != "package":
        return order_doc

    project = None
    if target_project_id:
        project = apply_package_purchase_to_project(
            user=user,
            project_id=target_project_id,
            package_code=package_code,
            package_name=package_name,
            stripe_session_id=stripe_session_id,
            stripe_payment_link_id=stripe_payment_link_id,
        )
    else:
        project = _find_matching_approved_project(
            user=user,
            email=order_doc.get("email"),
        )
        if project:
            project = apply_package_purchase_to_project(
                user=user,
                project_id=str(project.get("_id") or ""),
                package_code=package_code,
                package_name=package_name,
                stripe_session_id=stripe_session_id,
                stripe_payment_link_id=stripe_payment_link_id,
            )
        else:
            project = create_project_from_paid_order(
                user=user,
                package_code=package_code,
                package_name=package_name,
                stripe_session_id=stripe_session_id,
                stripe_payment_link_id=stripe_payment_link_id,
            )

    _link_order_to_project(
        orders=_get_orders_collection(),
        order_id=order_id,
        order_doc=order_doc,
        project=project,
    )
    return order_doc


def _serialize_order(order: dict[str, Any]) -> dict[str, Any]:
    package_code = _normalize_package_code(
        order.get("package_code") or order.get("package_slug")
    )

    return {
        "id": str(order["_id"]),
        "user_id": str(order["user_id"]),
        "email": order["email"],
        "package_code": package_code,
        "package_slug": package_code,
        "lane": order.get("lane") or order.get("package_lane") or _package_lane_for_code(package_code),
        "package_lane": order.get("package_lane") or order.get("lane") or _package_lane_for_code(package_code),
        "package_name": order.get("package_name", ""),
        "addon_code": order.get("addon_code"),
        "purchase_code": order.get("purchase_code"),
        "price_label": order.get("price_label", ""),
        "item_type": order.get("item_type", "package"),
        "billing_plan": order.get("billing_plan", "one_time"),
        "source": order.get("source", "stripe"),
        "status": order.get("status", "paid"),
        "project_id": str(order["project_id"]) if order.get("project_id") else None,
        "stripe_session_id": order.get("stripe_session_id"),
        "stripe_payment_link_id": order.get("stripe_payment_link_id"),
        "fulfillment_status": order.get("fulfillment_status"),
        "nft_credit_status": order.get("nft_credit_status"),
        "nft_credit_slot": order.get("nft_credit_slot"),
        "created_at": order["created_at"],
    }


def _validated_user_object_id(user: dict[str, Any]) -> ObjectId:
    user_id = _normalize(str(user.get("_id") or user.get("id") or user.get("user_id") or ""))
    if not ObjectId.is_valid(user_id):
        raise ValueError("Authenticated user id is invalid.")
    return ObjectId(user_id)


def _create_pending_public_checkout_order(
    *,
    user: dict[str, Any],
    package_code: str,
) -> dict[str, Any]:
    if package_code == "unknown" or not get_package(package_code):
        raise ValueError("Unknown package.")

    orders = _get_orders_collection()
    user_oid = _validated_user_object_id(user)
    existing = orders.find_one(
        {
            "user_id": user_oid,
            "package_code": package_code,
            "status": PENDING_PUBLIC_ORDER_STATUS,
            "source": "customer_checkout_pending",
        },
        sort=[("created_at", -1)],
    )
    if existing:
        return _serialize_order(existing)

    package = get_package(package_code) or {}
    order_doc = {
        "user_id": user_oid,
        "email": _normalize_email(user.get("email")),
        "package_code": package_code,
        "package_slug": package_code,
        "lane": _package_lane_for_code(package_code),
        "package_lane": _package_lane_for_code(package_code),
        "package_name": _normalize(package.get("display_name")) or package_code.replace("_", " ").title(),
        "price_label": _format_price_label(_base_package_price_cents(package_code), "one_time"),
        "item_type": "package",
        "billing_plan": "one_time",
        "source": "customer_checkout_pending",
        "status": PENDING_PUBLIC_ORDER_STATUS,
        "created_at": datetime.now(UTC),
    }
    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id
    return _serialize_order(order_doc)


def _create_verified_paid_package_order(
    *,
    user: dict[str, Any],
    session_id: str,
    requested_package_code: str = "",
) -> dict[str, Any]:
    orders = _get_orders_collection()
    existing = _find_order_by_session_id_for_customer(
        orders=orders,
        session_id=session_id,
        user=user,
    )
    if existing:
        return _serialize_order(existing)

    session = _retrieve_checkout_session(session_id)
    _ensure_session_belongs_to_user(user=user, session=session)
    purchase = _extract_verified_package_purchase_from_session(session)
    package_code = purchase["package_code"]
    if requested_package_code and requested_package_code != package_code:
        raise ValueError("Checkout session product and requested package do not match.")

    target_project_id = _extract_target_project_id(session)
    if target_project_id:
        entitlement = get_project_entitlement(target_project_id) or {}
        entitlement_status = _normalize(entitlement.get("status")).lower() or "active"
        entitlement_package = _normalize_package_code(entitlement.get("package_code"))
        if entitlement_status == "active" and entitlement_package == package_code:
            raise ValueError(
                "This workspace already has an active package entitlement. Invite members instead of purchasing again."
            )

    user_oid = _validated_user_object_id(user)
    order_doc = {
        "user_id": user_oid,
        "email": _normalize_email(user.get("email")),
        "package_code": package_code,
        "package_slug": package_code,
        "lane": _package_lane_for_code(package_code),
        "package_lane": _package_lane_for_code(package_code),
        "package_name": purchase["package_name"],
        "price_label": purchase["price_label"],
        "item_type": "package",
        "billing_plan": purchase["billing_plan"],
        "source": "stripe_verified",
        "status": "paid",
        "stripe_session_id": session_id,
        "created_at": datetime.now(UTC),
    }
    manual_mode = manual_fulfillment_mode_enabled()
    if manual_mode:
        order_doc["fulfillment_status"] = FULFILLMENT_PENDING
    _set_if_present(order_doc, "stripe_payment_link_id", purchase.get("stripe_payment_link_id"))
    _set_if_present(order_doc, "stripe_payment_intent_id", _normalize(session.get("payment_intent")) or None)
    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id

    if manual_mode:
        # Payment is verified and recorded, but package provisioning stays
        # manually controlled through the admin fulfillment queue.
        return _serialize_order(order_doc)

    order_doc = _attach_project_to_paid_package_order(
        order_id=result.inserted_id,
        order_doc=order_doc,
        user=user,
        package_code=package_code,
        package_name=purchase["package_name"],
        target_project_id=target_project_id,
        stripe_session_id=session_id,
        stripe_payment_link_id=purchase.get("stripe_payment_link_id"),
    )
    _trigger_package_provisioning()
    return _serialize_order(order_doc)


def create_order_for_user(user: dict[str, Any], payload: Any) -> dict[str, Any]:
    requested_package_code = _normalize_package_code(
        getattr(payload, "package_code", None) or getattr(payload, "package_slug", None)
    )
    target_project_id = _normalize(getattr(payload, "project_id", None))
    if target_project_id and requested_package_code != "unknown":
        entitlement = get_project_entitlement(target_project_id) or {}
        entitlement_status = _normalize(entitlement.get("status")).lower() or "active"
        entitlement_package = _normalize_package_code(entitlement.get("package_code"))
        if entitlement_status == "active" and entitlement_package == requested_package_code:
            raise ValueError(
                "This workspace already has an active package entitlement. Invite members instead of purchasing again."
            )

    stripe_session_id = _normalize(getattr(payload, "stripe_session_id", None))

    if stripe_session_id:
        return _create_verified_paid_package_order(
            user=user,
            session_id=stripe_session_id,
            requested_package_code=requested_package_code if requested_package_code != "unknown" else "",
        )

    return _create_pending_public_checkout_order(
        user=user,
        package_code=requested_package_code,
    )


def create_manual_order_for_admin(admin_user: dict[str, Any], payload: Any) -> dict[str, Any]:
    del admin_user, payload
    raise ValueError(
        "Manual paid-order creation is disabled. Record real payment through Stripe, "
        "or use the CEO package-grant action, which creates no paid order."
    )


def get_orders_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    orders = _get_orders_collection()
    docs = list(
        orders.find({"user_id": ObjectId(str(user["_id"]))}).sort("created_at", -1)
    )
    return [_serialize_order(doc) for doc in docs]


def repair_paid_package_order_access(limit: int = 500) -> dict[str, Any]:
    orders = _get_orders_collection()
    db = cast(Database, get_database())
    stats: dict[str, Any] = {
        "scanned": 0,
        "updated_orders": 0,
        "provisioned_projects": 0,
        "ensured_entitlements": 0,
        "skipped": 0,
        "problems": [],
    }

    cursor = (
        orders.find(
            {
                "status": {"$in": list(PAID_ORDER_STATUSES)},
                "$or": [
                    {"item_type": {"$exists": False}},
                    {"item_type": None},
                    {"item_type": ""},
                    {"item_type": "package"},
                ],
            }
        )
        .sort("created_at", -1)
        .limit(max(1, min(int(limit or 500), 1000)))
    )

    for order_doc in cursor:
        stats["scanned"] += 1
        order_id = order_doc["_id"]
        stripe_session_id = _normalize(order_doc.get("stripe_session_id"))
        if (
            not _is_authoritative_order_source(order_doc.get("source"))
            and not stripe_session_id
        ):
            stats["skipped"] += 1
            stats["problems"].append(
                {
                    "order_id": str(order_id),
                    "reason": "non_authoritative_paid_order",
                    "source": order_doc.get("source"),
                }
            )
            continue

        package_code = _normalize_package_code(
            order_doc.get("package_code") or order_doc.get("package_slug")
        )

        if not package_code or package_code == "unknown" or not get_package(package_code):
            stats["skipped"] += 1
            stats["problems"].append(
                {
                    "order_id": str(order_id),
                    "reason": "unknown_package",
                    "package": (
                        order_doc.get("package_code") or order_doc.get("package_slug")
                    ),
                }
            )
            continue

        update_fields: dict[str, Any] = {
            "package_code": package_code,
            "package_slug": package_code,
            "lane": _package_lane_for_code(package_code),
            "package_lane": _package_lane_for_code(package_code),
            "item_type": "package",
            "billing_plan": order_doc.get("billing_plan") or "one_time",
            "status": "paid",
        }

        user = _user_for_order(order_doc)
        if not user:
            orders.update_one({"_id": order_id}, {"$set": update_fields})
            stats["updated_orders"] += 1
            stats["skipped"] += 1
            stats["problems"].append(
                {"order_id": str(order_id), "reason": "missing_user"}
            )
            continue

        user_id = _coerce_object_id(user.get("_id") or user.get("id"))
        if user_id:
            update_fields["user_id"] = user_id

        project_id = _coerce_object_id(order_doc.get("project_id"))
        project = db.projects.find_one({"_id": project_id}) if project_id else None
        if not project:
            project = _find_existing_project_for_paid_order(
                db=db,
                order_doc=order_doc,
                user=user,
                package_code=package_code,
            )
            if project:
                project_id = _coerce_object_id(project.get("_id"))
                update_fields["project_id"] = project.get("_id")

        if project:
            apply_package_purchase_to_project(
                user=user,
                project_id=str(project_id),
                package_code=package_code,
                package_name=order_doc.get("package_name") or package_code,
                stripe_session_id=order_doc.get("stripe_session_id"),
                stripe_payment_link_id=order_doc.get("stripe_payment_link_id"),
            )
            stats["ensured_entitlements"] += 1
        else:
            project = create_project_from_paid_order(
                user=user,
                package_code=package_code,
                package_name=order_doc.get("package_name") or package_code,
                stripe_session_id=order_doc.get("stripe_session_id"),
                stripe_payment_link_id=order_doc.get("stripe_payment_link_id"),
            )
            if project:
                update_fields["project_id"] = project.get("_id")
                stats["provisioned_projects"] += 1
                stats["ensured_entitlements"] += 1
            else:
                stats["skipped"] += 1
                stats["problems"].append(
                    {
                        "order_id": str(order_id),
                        "reason": "project_provisioning_failed",
                    }
                )

        orders.update_one({"_id": order_id}, {"$set": update_fields})
        stats["updated_orders"] += 1

    return stats


def list_recent_orders(
    *,
    limit: int = 100,
    status: str = "",
    search: str = "",
) -> list[dict[str, Any]]:
    orders = _get_orders_collection()

    normalized_status = _normalize(status).lower()
    normalized_search = _normalize(search)

    query: dict[str, Any] = {}
    if normalized_status:
        query["status"] = normalized_status

    if normalized_search:
        regex = {"$regex": re.escape(normalized_search), "$options": "i"}
        query["$or"] = [
            {"email": regex},
            {"package_name": regex},
            {"package_code": regex},
            {"package_slug": regex},
            {"price_label": regex},
            {"stripe_session_id": regex},
            {"stripe_payment_link_id": regex},
        ]

    docs = list(orders.find(query).sort("created_at", -1).limit(max(1, min(limit, 500))))
    return [_serialize_order(doc) for doc in docs]


def ensure_order_indexes() -> None:
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
            if unique:
                raise
            logger.warning("Could not create optional orders index %s.", name)

    _ensure_index([("user_id", 1)], name="user_id_1")
    _ensure_index([("owner_user_id", 1)], name="owner_user_id_1")
    _ensure_index([("email", 1)], name="email_1")
    _ensure_index([("package_code", 1)], name="package_code_1")
    _ensure_index([("package_slug", 1)], name="package_slug_1")
    _ensure_index([("item_type", 1)], name="item_type_1")
    _ensure_index([("addon_code", 1)], name="addon_code_1")
    _ensure_index([("billing_plan", 1)], name="billing_plan_1")
    _ensure_index([("created_at", -1)], name="created_at_-1")
    # project_id is queried on every workspace access check; index is required to
    # avoid full collection scans that cause request timeouts.
    _ensure_index([("project_id", 1)], name="project_id_1")
    _ensure_index(
        [("project_id", 1), ("addon_code", 1), ("nft_credit_status", 1)],
        name="project_id_1_addon_code_1_nft_credit_status_1",
    )
    # The value combines project id and mint sequence (for example mint:1).
    # A sparse unique index closes concurrent duplicate-checkout races without
    # constraining metadata-revision purchases.
    _ensure_index(
        [("nft_credit_slot_key", 1)],
        name="nft_credit_slot_key_1",
        unique=True,
        sparse=True,
    )
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
    _ensure_index(
        [("manual_idempotency_key", 1)],
        name="manual_idempotency_key_1",
        unique=True,
        sparse=True,
    )


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
    return (
        ((event.get("data") or {}).get("object") or {})
        if isinstance(event, dict)
        else {}
    )


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


def _extract_customer_name_from_session(session: dict[str, Any]) -> str:
    customer_details = session.get("customer_details") or {}
    shipping_details = session.get("shipping_details") or {}
    metadata = session.get("metadata") or {}

    return _normalize(
        customer_details.get("name")
        or shipping_details.get("name")
        or metadata.get("full_name")
        or metadata.get("name")
        or metadata.get("customer_name")
    )


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


def _extract_billing_plan_from_session(session: dict[str, Any]) -> str:
    line_items = ((session.get("line_items") or {}).get("data")) or []
    if not line_items:
        return "one_time"

    first_item = line_items[0] or {}
    price_obj = first_item.get("price") or {}
    recurring = price_obj.get("recurring") or {}

    interval = str(recurring.get("interval") or "").strip().lower()
    if interval == "month":
        return "monthly"
    if interval == "year":
        return "yearly"

    return "one_time"


def _extract_checkout_context(session: dict[str, Any]) -> dict[str, str]:
    raw_reference = _normalize(session.get("client_reference_id"))
    if not raw_reference:
        return {}
    if not raw_reference.startswith("tol:"):
        return {}
    try:
        parsed = dict(parse_qsl(raw_reference[4:], keep_blank_values=False))
    except Exception:
        return {}

    context: dict[str, str] = {}
    if parsed.get("u"):
        context["user_id"] = _normalize(parsed.get("u"))
    if parsed.get("p"):
        context["project_id"] = _normalize(parsed.get("p"))
    if parsed.get("t"):
        context["item_type"] = _normalize(parsed.get("t")).lower()
    if parsed.get("k"):
        raw_code = _normalize(parsed.get("k")).lower().replace("-", "_").replace(" ", "_")
        context["package_code"] = (
            normalize_addon_code(raw_code)
            if context.get("item_type") == "addon"
            else _normalize_package_code(raw_code)
        )
    if parsed.get("b"):
        context["billing_interval"] = _normalize(parsed.get("b")).lower()
    if parsed.get("c"):
        context["campaign"] = _normalize(parsed.get("c")).upper()
    return {k: v for k, v in context.items() if v}


def _format_price_label(amount_subtotal: Any, billing_plan: str) -> str:
    if not isinstance(amount_subtotal, int):
        return "paid"

    amount = amount_subtotal / 100

    if billing_plan == "monthly":
        return f"${amount:,.2f}/month"
    if billing_plan == "yearly":
        return f"${amount:,.2f}/year"

    return f"${amount:,.2f}"


def _normalize_currency(value: Any) -> str:
    return _normalize(str(value or "")).lower()


def _base_package_price_cents(package_code: str) -> int:
    package = get_package(package_code) or {}
    base_price = package.get("base_price_usd")
    try:
        return int(round(float(base_price) * 100))
    except Exception:
        return 0


def _match_package_code_from_product(
    *,
    raw_code: str,
    product_name: str,
) -> str:
    if raw_code:
        normalized = _normalize_package_code(raw_code)
        if normalized != "unknown" and get_package(normalized):
            return normalized
    normalized_from_name = _normalize_package_code(product_name)
    if normalized_from_name != "unknown" and get_package(normalized_from_name):
        return normalized_from_name
    return "unknown"


def _extract_verified_package_purchase_from_session(session: dict[str, Any]) -> dict[str, Any]:
    session_status = _normalize(session.get("status")).lower()
    if session_status == "expired":
        raise ValueError("Checkout session has expired.")

    if _normalize(session.get("payment_status")).lower() != "paid":
        raise ValueError("Checkout session is not paid.")

    line_items = ((session.get("line_items") or {}).get("data")) or []
    if not line_items:
        raise ValueError("Checkout session has no line items.")

    first_item = line_items[0] or {}
    price_obj = first_item.get("price") or {}
    if not price_obj:
        raise ValueError("Checkout session line item is missing price data.")

    price_id = _normalize(price_obj.get("id"))
    if not price_id:
        raise ValueError("Checkout session line item has unknown price.")

    product_obj = price_obj.get("product") or {}
    product_id = _normalize(product_obj.get("id"))
    if not product_id:
        raise ValueError("Checkout session line item has unknown product.")

    raw_package_code = _normalize(
        ((session.get("metadata") or {}).get("package_code"))
        or ((session.get("metadata") or {}).get("package_slug"))
        or ((product_obj.get("metadata") or {}).get("package_code"))
        or ((product_obj.get("metadata") or {}).get("package_slug"))
    )
    product_name = _normalize(
        product_obj.get("name")
        or first_item.get("description")
        or ((session.get("metadata") or {}).get("package_name"))
    )
    package_code = _match_package_code_from_product(
        raw_code=raw_package_code,
        product_name=product_name,
    )
    if package_code == "unknown":
        raise ValueError("Checkout session product is not an approved Tomb of Light package.")

    package = get_package(package_code) or {}
    amount_cents = price_obj.get("unit_amount")
    if not isinstance(amount_cents, int):
        raise ValueError("Checkout session line item has unknown price amount.")

    currency = _normalize_currency(price_obj.get("currency") or session.get("currency"))
    if not currency:
        raise ValueError("Checkout session line item currency is missing.")

    expected_cents = _base_package_price_cents(package_code)
    if expected_cents <= 0:
        raise ValueError("Package catalog price is not configured.")
    if currency != "usd" or amount_cents != expected_cents:
        raise ValueError("Checkout session product and price do not match the approved package catalog.")

    amount_total = session.get("amount_total")
    if isinstance(amount_total, int) and amount_total != expected_cents:
        raise ValueError("Checkout session amount does not match expected package total.")

    billing_plan = "one_time"
    package_name = _normalize(package.get("display_name")) or package_code.replace("_", " ").title()

    return {
        "package_code": package_code,
        "package_name": package_name,
        "price_label": _format_price_label(expected_cents, billing_plan),
        "item_type": "package",
        "billing_plan": billing_plan,
        "currency": currency,
        "amount_cents": expected_cents,
        "stripe_payment_link_id": _normalize(session.get("payment_link")) or None,
        "price_id": price_id,
        "product_id": product_id,
    }


def _normalized_catalog_product_name(value: Any) -> str:
    normalized = _normalize(value).lower().replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^add\s*-?\s*on\s*-\s*", "", normalized)
    return normalized.strip()


def _match_addon_code_from_product(
    *,
    raw_code: str,
    product_name: str,
) -> str:
    candidate = normalize_addon_code(raw_code)
    addon_codes = tuple(get_addon_catalog())
    if candidate not in addon_codes:
        candidate = ""

    normalized_name = _normalized_catalog_product_name(product_name)
    name_matches = [
        code
        for code in addon_codes
        if normalized_name
        == _normalized_catalog_product_name((get_addon(code) or {}).get("display_name"))
    ]
    if len(name_matches) != 1:
        return ""
    if candidate and candidate != name_matches[0]:
        return ""
    return candidate or name_matches[0]


def _extract_verified_catalog_purchase_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Verify a base-package or add-on purchase against the server catalog."""

    metadata = session.get("metadata") or {}
    context = _extract_checkout_context(session)
    requested_type = _normalize(metadata.get("item_type") or context.get("item_type")).lower()

    line_items = ((session.get("line_items") or {}).get("data")) or []
    first_item = line_items[0] if line_items else {}
    price_obj = (first_item or {}).get("price") or {}
    product_obj = price_obj.get("product") or {}
    product_name = _normalize(
        product_obj.get("name")
        or (first_item or {}).get("description")
        or metadata.get("package_name")
    )
    raw_code = _normalize(
        metadata.get("addon_code")
        or metadata.get("package_code")
        or metadata.get("package_slug")
        or (product_obj.get("metadata") or {}).get("addon_code")
        or (product_obj.get("metadata") or {}).get("package_code")
        or context.get("package_code")
    )
    addon_code = _match_addon_code_from_product(
        raw_code=raw_code,
        product_name=product_name,
    )
    if requested_type == "addon" or addon_code:
        session_status = _normalize(session.get("status")).lower()
        if session_status == "expired":
            raise ValueError("Checkout session has expired.")
        if _normalize(session.get("payment_status")).lower() != "paid":
            raise ValueError("Checkout session is not paid.")
        if not line_items or not price_obj or not product_obj:
            raise ValueError("Checkout session is missing expanded product and price data.")
        if len(line_items) != 1 or int((first_item or {}).get("quantity") or 1) != 1:
            raise ValueError("Add-on checkout must contain exactly one item.")
        if not addon_code:
            raise ValueError("Checkout product is not an approved Tomb of Light add-on.")

        addon = get_addon(addon_code) or {}
        amount_cents = price_obj.get("unit_amount")
        expected_cents = int(round(float(addon.get("price_usd") or 0) * 100))
        currency = _normalize_currency(price_obj.get("currency") or session.get("currency"))
        if expected_cents <= 0 or currency != "usd" or amount_cents != expected_cents:
            raise ValueError("Checkout product and price do not match the approved add-on catalog.")
        amount_total = session.get("amount_total")
        if isinstance(amount_total, int) and amount_total != expected_cents:
            raise ValueError("Checkout session amount does not match expected add-on total.")

        price_id = _normalize(price_obj.get("id"))
        product_id = _normalize(product_obj.get("id"))
        if not price_id or not product_id:
            raise ValueError("Checkout session add-on has unknown Stripe catalog identifiers.")
        addon_billing_plan = _extract_billing_plan_from_session(session)
        return {
            "package_code": addon_code,
            "addon_code": addon_code,
            "package_name": _normalize(addon.get("display_name")),
            "price_label": _format_price_label(expected_cents, addon_billing_plan),
            "item_type": "addon",
            "billing_plan": addon_billing_plan,
            "currency": currency,
            "amount_cents": expected_cents,
            "stripe_payment_link_id": _normalize(session.get("payment_link")) or None,
            "price_id": price_id,
            "product_id": product_id,
        }

    return _extract_verified_package_purchase_from_session(session)


def _ensure_session_belongs_to_user(
    *,
    user: dict[str, Any],
    session: dict[str, Any],
) -> None:
    session_email = _extract_email_from_session(session)
    user_email = _normalize_email(user.get("email"))
    if not session_email or not user_email or session_email != user_email:
        raise ValueError("Checkout session email does not match authenticated customer.")

    metadata = session.get("metadata") or {}
    context = _extract_checkout_context(session)
    metadata_user_id = _normalize(metadata.get("user_id") or context.get("user_id"))
    current_user_id = _normalize(str(user.get("_id") or user.get("id") or user.get("user_id") or ""))
    if metadata_user_id and current_user_id and metadata_user_id != current_user_id:
        raise ValueError("Checkout session user association mismatch.")

    session_customer_id = _normalize(session.get("customer"))
    user_customer_id = _normalize(user.get("stripe_customer_id"))
    if session_customer_id and user_customer_id and session_customer_id != user_customer_id:
        raise ValueError("Checkout session customer does not match authenticated customer.")


def _find_order_by_session_id_for_customer(
    *,
    orders: Collection,
    session_id: str,
    user: dict[str, Any],
) -> dict[str, Any] | None:
    existing = orders.find_one({"stripe_session_id": session_id})
    if not existing:
        return None

    existing_user_id = _normalize(str(existing.get("user_id") or ""))
    current_user_id = _normalize(str(user.get("_id") or user.get("id") or user.get("user_id") or ""))
    existing_email = _normalize_email(existing.get("email"))
    current_email = _normalize_email(user.get("email"))
    if (
        (existing_user_id and current_user_id and existing_user_id != current_user_id)
        or (existing_email and current_email and existing_email != current_email)
    ):
        raise ValueError("Checkout session is already associated with another customer.")
    return existing

def _schedule_maintenance_start(
    *,
    project_id: str,
    billing_plan: str,
    stripe_subscription_id: str | None = None,
    stripe_customer_id: str | None = None,
) -> None:
    plan = _normalize(billing_plan).lower()
    if plan not in {"monthly", "yearly"}:
        return

    now = datetime.now(UTC)
    start_at = now + timedelta(days=MAINTENANCE_START_DELAY_DAYS)
    update_project_entitlement_maintenance(
        project_id=project_id,
        maintenance_plan=plan,
        maintenance_status="scheduled",
        maintenance_scheduled_start_at=start_at,
        maintenance_stripe_subscription_id=_normalize(stripe_subscription_id) or None,
        maintenance_stripe_customer_id=_normalize(stripe_customer_id) or None,
        maintenance_stripe_status="incomplete",
    )


def _extract_target_project_id(session: dict[str, Any]) -> str:
    metadata = session.get("metadata") or {}
    context = _extract_checkout_context(session)
    return _normalize(
        metadata.get("project_id")
        or metadata.get("upgrade_project_id")
        or metadata.get("existing_project_id")
        or metadata.get("target_project_id")
        or context.get("project_id")
    )


def _infer_purchase_fields(session: dict[str, Any]) -> tuple[str, str, str, str, str]:
    metadata = session.get("metadata") or {}
    context = _extract_checkout_context(session)

    raw_code = (
        metadata.get("package_code")
        or metadata.get("package_slug")
        or metadata.get("package")
        or context.get("package_code")
    )
    package_name = _normalize(metadata.get("package_name"))
    price_label = _normalize(metadata.get("price_label"))
    item_type = _normalize(
        metadata.get("item_type")
        or metadata.get("type")
        or context.get("item_type")
    ) or "package"
    billing_plan = (
        _normalize(metadata.get("billing_plan"))
        or _normalize(context.get("billing_interval"))
        or _extract_billing_plan_from_session(session)
    )

    if raw_code:
        package_code = _normalize_package_code(raw_code)
        if package_name and price_label:
            return item_type, package_code, package_name, price_label, billing_plan
        if context.get("item_type") or context.get("billing_interval"):
            fallback_name = package_name or package_code.replace("_", " ").title()
            fallback_price_label = price_label or _format_price_label(
                session.get("amount_subtotal"),
                billing_plan,
            )
            return (
                item_type,
                package_code,
                fallback_name,
                fallback_price_label,
                billing_plan,
            )

    product_name = _extract_product_name_from_session(session) or ""
    name_lower = product_name.lower()
    amount_subtotal = session.get("amount_subtotal")
    inferred_billing_plan = _extract_billing_plan_from_session(session)

    if "maintenance" in name_lower:
        base_code = "unknown"
        base_name = "Maintenance"

        if "legacy snapshot" in name_lower:
            base_code = "legacy_snapshot"
            base_name = "Legacy Snapshot Maintenance"
        elif "legacy portrait intro" in name_lower:
            base_code = "legacy_portrait_intro"
            base_name = "Legacy Portrait Intro Maintenance"
        elif "digital legacy portrait" in name_lower:
            base_code = "digital_legacy_portrait"
            base_name = "Digital Legacy Portrait Maintenance"
        elif "household foundation" in name_lower or "starter" in name_lower:
            base_code = "household_foundation"
            base_name = "Household Foundation Maintenance"
        elif "heirloom" in name_lower:
            base_code = "heirloom_legacy_tree"
            base_name = "Heirloom Legacy Tree Maintenance"
        elif "legacy plus" in name_lower:
            base_code = "legacy_plus"
            base_name = "Legacy Plus Maintenance"
        elif "family estate concierge" in name_lower:
            base_code = "family_estate_concierge"
            base_name = "Family Estate Concierge Maintenance"
        elif "command structure network" in name_lower:
            base_code = "command_structure_network"
            base_name = "Command Structure Network Maintenance"

        suffix = "monthly" if inferred_billing_plan == "monthly" else "yearly" if inferred_billing_plan == "yearly" else "one_time"
        return (
            "maintenance",
            f"{base_code}_{suffix}",
            base_name,
            _format_price_label(amount_subtotal, inferred_billing_plan),
            inferred_billing_plan,
        )

    add_on_patterns = [
        ("white-glove archive support", "white_glove_archive_support", "White-Glove Archive Support"),
        ("command report", "command_report_addon", "Command Report Add-On"),
        ("extra upload", "extra_upload_pack", "Extra Upload Pack"),
        ("extra storage", "extra_storage", "Extra Storage"),
        ("portrait polish", "portrait_polish", "Portrait Polish"),
        ("tribute narration", "tribute_narration", "Tribute Narration"),
        ("extra mapped person", "extra_mapped_person", "Extra Mapped Person"),
        ("extra zoom layer", "extra_zoom_layer", "Extra Zoom Layer"),
        ("additional narration minute", "additional_narration_minute", "Additional Narration Minute"),
        ("on-site photo scanning", "on_site_photo_scanning", "On-Site Photo Scanning"),
        ("extra linked household", "extra_linked_household", "Extra Linked Household"),
        ("extra branch", "extra_branch", "Extra Branch"),
        ("extra organization node", "extra_org_node", "Extra Organization Node"),
        ("extra organization level", "extra_org_level", "Extra Organization Level"),
        ("extra admin seat", "extra_admin_seat", "Extra Admin Seat"),
    ]

    for pattern, code, name in add_on_patterns:
        if pattern in name_lower:
            return (
                "addon",
                code,
                name,
                _format_price_label(amount_subtotal, "one_time"),
                "one_time",
            )

    package_patterns = [
        ("family estate concierge", "family_estate_concierge", "Family Estate Concierge"),
        ("command structure network", "command_structure_network", "Command Structure Network"),
        ("legacy snapshot", "legacy_snapshot", "Legacy Snapshot"),
        ("legacy portrait intro", "legacy_portrait_intro", "Legacy Portrait Intro"),
        ("digital legacy portrait", "digital_legacy_portrait", "Digital Legacy Portrait"),
        ("household foundation", "household_foundation", "Household Foundation"),
        ("starter family tree", "household_foundation", "Household Foundation"),
        ("heirloom legacy tree", "heirloom_legacy_tree", "Heirloom Legacy Tree"),
        ("legacy plus", "legacy_plus", "Legacy Plus"),
    ]

    for pattern, code, name in package_patterns:
        if pattern in name_lower:
            return (
                "package",
                code,
                name,
                _format_price_label(amount_subtotal, "one_time"),
                "one_time",
            )

    return (
        "package",
        _normalize_package_code(raw_code or "unknown"),
        product_name or "Tomb of Light Purchase",
        _format_price_label(amount_subtotal, inferred_billing_plan),
        inferred_billing_plan,
    )


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


def _record_escalated_addon_payment(
    *,
    user: dict[str, Any],
    email: str,
    session: dict[str, Any],
    purchase: dict[str, Any],
    reason: str,
    project_id: str = "",
) -> dict[str, Any]:
    """Preserve a paid but ineligible add-on without granting access or credit."""

    orders = _get_orders_collection()
    session_id = _normalize(session.get("id"))
    existing = orders.find_one({"stripe_session_id": session_id})
    if existing:
        return {
            "order_id": str(existing["_id"]),
            "existing": True,
            "reason": "addon_payment_escalated",
            "error": reason,
            "session_id": session_id,
        }

    addon_code = normalize_addon_code(purchase.get("addon_code"))
    is_nft_addon = addon_code in NFT_ADDON_CODES
    document: dict[str, Any] = {
        "user_id": ObjectId(str(user["_id"])),
        "email": email,
        "package_code": addon_code,
        "package_slug": addon_code,
        "addon_code": addon_code,
        "purchase_code": addon_code,
        "package_name": purchase.get("package_name"),
        "price_label": purchase.get("price_label"),
        "item_type": "addon",
        "billing_plan": "one_time",
        "source": "stripe_webhook",
        "status": "paid",
        "fulfillment_status": FULFILLMENT_ESCALATED,
        "fulfillment_error": reason,
        "paid_addon_verified": False,
        "stripe_session_id": session_id,
        "stripe_payment_link_id": _normalize(session.get("payment_link")) or None,
        "stripe_payment_intent_id": _normalize(session.get("payment_intent")) or None,
        "stripe_subscription_id": _normalize(session.get("subscription")) or None,
        "amount_total_cents": int(purchase.get("amount_cents") or session.get("amount_total") or 0),
        "currency": _normalize(purchase.get("currency") or session.get("currency")) or "usd",
        "payment_verified_at": datetime.now(UTC),
        "payment_verification": {"method": "stripe_webhook", "verified": True},
        "created_at": datetime.now(UTC),
    }
    if is_nft_addon:
        document.update(
            {
                "nft_addon_verified": False,
                "nft_credit_status": "blocked",
                "nft_addon_checkout_does_not_auto_mint": True,
            }
        )
    project_oid = _to_object_id(project_id)
    if project_oid is not None:
        document["project_id"] = project_oid
    result = orders.insert_one(document)
    return {
        "order_id": str(result.inserted_id),
        "existing": False,
        "reason": "addon_payment_escalated",
        "error": reason,
        "session_id": session_id,
        "project_id": str(project_oid) if project_oid is not None else None,
    }


def upsert_order_from_stripe_event(event: dict[str, Any]) -> dict[str, Any]:
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

    try:
        purchase = _extract_verified_catalog_purchase_from_session(session)
    except ValueError as exc:
        return {
            "order_id": None,
            "reason": "invalid_checkout_session",
            "error": str(exc),
            "type": event_type,
            "session_id": session_id,
        }

    email = _extract_email_from_session(session) or _get_email_from_event(event)
    if not email:
        return {
            "order_id": None,
            "reason": "no_email_in_checkout_session",
            "type": event_type,
            "session_id": session_id,
        }

    user = _get_user_by_email(email) or create_pending_checkout_user(
        email,
        full_name=_extract_customer_name_from_session(session),
    )
    if not user:
        return {
            "order_id": None,
            "reason": "no_matching_user",
            "type": event_type,
            "session_id": session_id,
            "email": email,
        }

    try:
        _ensure_session_belongs_to_user(user=user, session=session)
    except ValueError as exc:
        return {
            "order_id": None,
            "reason": "customer_association_mismatch",
            "error": str(exc),
            "type": event_type,
            "session_id": session_id,
            "email": email,
        }

    item_type = purchase["item_type"]
    addon_code = normalize_addon_code(purchase.get("addon_code"))
    orders = _get_orders_collection()
    existing_session_order = orders.find_one({"stripe_session_id": session_id})
    if item_type == "addon" and existing_session_order:
        existing_user_id = _normalize(str(existing_session_order.get("user_id") or ""))
        incoming_user_id = _normalize(
            str(user.get("_id") or user.get("id") or user.get("user_id") or "")
        )
        existing_email = _normalize_email(existing_session_order.get("email"))
        if (
            (existing_user_id and incoming_user_id and existing_user_id != incoming_user_id)
            or (existing_email and existing_email != email)
        ):
            return {
                "order_id": None,
                "reason": "session_already_associated_with_another_customer",
                "type": event_type,
                "session_id": session_id,
                "email": email,
            }
        existing_addon_code = normalize_addon_code(
            existing_session_order.get("addon_code")
            or existing_session_order.get("purchase_code")
        )
        if existing_addon_code != addon_code:
            return {
                "order_id": None,
                "reason": "session_already_associated_with_another_product",
                "type": event_type,
                "session_id": session_id,
                "email": email,
            }
        return {
            "order_id": str(existing_session_order["_id"]),
            "existing": True,
            "type": event_type,
            "session_id": session_id,
            "email": email,
            "package_code": existing_session_order.get("package_code"),
            "addon_code": existing_addon_code,
            "item_type": "addon",
            "billing_plan": existing_session_order.get("billing_plan") or "one_time",
            "project_id": (
                str(existing_session_order["project_id"])
                if existing_session_order.get("project_id")
                else None
            ),
            "nft_credit_status": existing_session_order.get("nft_credit_status"),
        }

    target_project_id = _extract_target_project_id(session)
    target_project: dict[str, Any] | None = None
    if item_type == "addon":
        if not target_project_id:
            return _record_escalated_addon_payment(
                user=user,
                email=email,
                session=session,
                purchase=purchase,
                reason="Add-on payment is missing required customer project context.",
            )
        try:
            if addon_code in NFT_ADDON_CODES:
                target_project = validate_nft_addon_purchase_target(
                    user=user,
                    project_id=target_project_id,
                    addon_code=addon_code,
                )
            else:
                target_project = validate_paid_addon_purchase_target(
                    user=user,
                    project_id=target_project_id,
                    addon_code=addon_code,
                )
        except ValueError as exc:
            return _record_escalated_addon_payment(
                user=user,
                email=email,
                session=session,
                purchase=purchase,
                reason=str(exc),
                project_id=target_project_id,
            )

    customer_id = _normalize(session.get("customer"))
    if customer_id:
        try:
            store_stripe_customer_reference(
                user_id=str(user.get("_id") or ""),
                email=email,
                customer_id=customer_id,
            )
        except Exception:
            pass

    checkout_context = _extract_checkout_context(session)
    campaign = _normalize((session.get("metadata") or {}).get("campaign") or checkout_context.get("campaign")).upper()

    purchase_code = purchase["package_code"]
    package_code = purchase_code
    if target_project is not None:
        package_code = _normalize_package_code(
            target_project.get("package_code")
            or target_project.get("package_slug")
            or target_project.get("package_type")
        )
    package_name = purchase["package_name"]
    price_label = purchase["price_label"]
    billing_plan = purchase["billing_plan"]
    stripe_payment_link_id = purchase["stripe_payment_link_id"]

    existing = orders.find_one({"stripe_session_id": session_id})
    if existing:
        existing_user_id = _normalize(str(existing.get("user_id") or ""))
        incoming_user_id = _normalize(str(user.get("_id") or user.get("id") or user.get("user_id") or ""))
        existing_email = _normalize_email(existing.get("email"))
        if (
            (existing_user_id and incoming_user_id and existing_user_id != incoming_user_id)
            or (existing_email and existing_email != email)
        ):
            return {
                "order_id": None,
                "reason": "session_already_associated_with_another_customer",
                "type": event_type,
                "session_id": session_id,
                "email": email,
            }
        update_fields: dict[str, Any] = {
            "email": email,
            "package_code": package_code,
            "package_slug": package_code,
            "lane": _package_lane_for_code(package_code),
            "package_lane": _package_lane_for_code(package_code),
            "package_name": package_name,
            "price_label": price_label,
            "item_type": item_type,
            "billing_plan": billing_plan,
            "source": "stripe_webhook",
            "status": "paid",
            "stripe_session_id": session_id,
            "amount_total_cents": int(purchase.get("amount_cents") or session.get("amount_total") or 0),
            "currency": _normalize(purchase.get("currency") or session.get("currency")) or "usd",
        }
        if item_type == "addon" and target_project is not None:
            update_fields.update(
                {
                    "project_id": target_project["_id"],
                    "addon_code": addon_code,
                    "purchase_code": purchase_code,
                    "paid_addon_verified": True,
                    "payment_verified_at": datetime.now(UTC),
                    "payment_verification": {"method": "stripe_webhook", "verified": True},
                }
            )
            if addon_code in NFT_ADDON_CODES:
                update_fields.update(
                    {
                        "nft_addon_verified": True,
                        "nft_addon_checkout_does_not_auto_mint": True,
                    }
                )
                _set_if_present(
                    update_fields,
                    "nft_credit_slot",
                    target_project.get("_nft_credit_slot"),
                )
                _set_if_present(
                    update_fields,
                    "nft_credit_slot_key",
                    target_project.get("_nft_credit_slot_key"),
                )
                if not _normalize(existing.get("nft_credit_status")):
                    update_fields["nft_credit_status"] = "available"
            elif not existing.get("fulfillment_status"):
                update_fields["fulfillment_status"] = FULFILLMENT_PENDING
        _set_if_present(update_fields, "stripe_payment_link_id", stripe_payment_link_id)
        _set_if_present(update_fields, "campaign", campaign)
        _set_if_present(update_fields, "stripe_payment_intent_id", _normalize(session.get("payment_intent")) or None)
        _set_if_present(update_fields, "stripe_subscription_id", _normalize(session.get("subscription")) or None)
        manual_mode = manual_fulfillment_mode_enabled()
        if (
            manual_mode
            and item_type == "package"
            and not existing.get("fulfillment_status")
            and not existing.get("project_id")
        ):
            update_fields["fulfillment_status"] = FULFILLMENT_PENDING
        orders.update_one({"_id": existing["_id"]}, {"$set": update_fields})

        order_doc = orders.find_one({"_id": existing["_id"]}) or {
            **existing,
            **update_fields,
        }
        if item_type == "package" and not manual_mode and not order_doc.get("project_id"):
            order_doc = _attach_project_to_paid_package_order(
                order_id=existing["_id"],
                order_doc=order_doc,
                user=user,
                package_code=package_code,
                package_name=package_name,
                target_project_id=_extract_target_project_id(session),
                stripe_session_id=session_id,
                stripe_payment_link_id=stripe_payment_link_id,
            )
        if item_type == "package" and not manual_mode:
            _trigger_package_provisioning()

        return {
            "order_id": str(existing["_id"]),
            "existing": True,
            "type": event_type,
            "session_id": session_id,
            "email": email,
            "package_code": package_code,
            "item_type": item_type,
            "billing_plan": billing_plan,
            "project_id": str(order_doc["project_id"]) if order_doc.get("project_id") else None,
        }

    order_doc = {
        "user_id": ObjectId(str(user["_id"])),
        "email": email,
        "package_code": package_code,
        "package_slug": package_code,
        "lane": _package_lane_for_code(package_code),
        "package_lane": _package_lane_for_code(package_code),
        "package_name": package_name,
        "price_label": price_label,
        "item_type": item_type,
        "billing_plan": billing_plan,
        "source": "stripe_webhook",
        "status": "paid",
        "stripe_session_id": session_id,
        "amount_total_cents": int(purchase.get("amount_cents") or session.get("amount_total") or 0),
        "currency": _normalize(purchase.get("currency") or session.get("currency")) or "usd",
        "created_at": datetime.now(UTC),
    }
    if item_type == "addon" and target_project is not None:
        order_doc.update(
            {
                "project_id": target_project["_id"],
                "addon_code": addon_code,
                "purchase_code": purchase_code,
                "paid_addon_verified": True,
                "payment_verified_at": datetime.now(UTC),
                "payment_verification": {"method": "stripe_webhook", "verified": True},
            }
        )
        if addon_code in NFT_ADDON_CODES:
            order_doc.update(
                {
                    "nft_addon_verified": True,
                    "nft_addon_checkout_does_not_auto_mint": True,
                    "nft_credit_status": "available",
                }
            )
            _set_if_present(
                order_doc,
                "nft_credit_slot",
                target_project.get("_nft_credit_slot"),
            )
            _set_if_present(
                order_doc,
                "nft_credit_slot_key",
                target_project.get("_nft_credit_slot_key"),
            )
        else:
            order_doc["fulfillment_status"] = FULFILLMENT_PENDING
    manual_mode = manual_fulfillment_mode_enabled()
    if manual_mode and item_type == "package":
        order_doc["fulfillment_status"] = FULFILLMENT_PENDING
    _set_if_present(order_doc, "stripe_payment_link_id", stripe_payment_link_id)
    _set_if_present(order_doc, "campaign", campaign)
    _set_if_present(order_doc, "stripe_payment_intent_id", _normalize(session.get("payment_intent")) or None)
    _set_if_present(order_doc, "stripe_subscription_id", _normalize(session.get("subscription")) or None)

    try:
        result = orders.insert_one(order_doc)
    except DuplicateKeyError:
        raced = orders.find_one({"stripe_session_id": session_id})
        if raced is not None:
            return {
                "order_id": str(raced["_id"]),
                "existing": True,
                "type": event_type,
                "session_id": session_id,
                "email": email,
                "package_code": raced.get("package_code"),
                "item_type": raced.get("item_type"),
                "billing_plan": raced.get("billing_plan"),
                "project_id": str(raced["project_id"]) if raced.get("project_id") else None,
            }
        if item_type != "addon":
            raise
        order_doc.pop("nft_credit_slot", None)
        order_doc.pop("nft_credit_slot_key", None)
        order_doc.update(
            {
                "nft_addon_verified": False,
                "nft_credit_status": "blocked",
                "fulfillment_status": FULFILLMENT_ESCALATED,
                "fulfillment_error": (
                    "A paid NFT mint credit already exists for this project and mint sequence."
                ),
            }
        )
        result = orders.insert_one(order_doc)
        order_doc["_id"] = result.inserted_id
        return {
            "order_id": str(result.inserted_id),
            "existing": False,
            "reason": "duplicate_nft_mint_credit_payment_escalated",
            "error": order_doc["fulfillment_error"],
            "type": event_type,
            "session_id": session_id,
            "email": email,
            "package_code": package_code,
            "addon_code": addon_code,
            "item_type": item_type,
            "billing_plan": billing_plan,
            "project_id": str(order_doc["project_id"]),
        }
    order_doc["_id"] = result.inserted_id

    if item_type == "package" and not manual_mode:
        target_project_id = _extract_target_project_id(session)
        order_doc = _attach_project_to_paid_package_order(
            order_id=result.inserted_id,
            order_doc=order_doc,
            user=user,
            package_code=package_code,
            package_name=package_name,
            target_project_id=target_project_id,
            stripe_session_id=session_id,
            stripe_payment_link_id=stripe_payment_link_id,
        )
    elif item_type == "maintenance":
        target_project_id = _extract_target_project_id(session)
        if target_project_id:
            project_oid = _to_object_id(target_project_id)
            if project_oid is not None:
                orders.update_one(
                    {"_id": result.inserted_id},
                    {"$set": {"project_id": project_oid}},
                )
                order_doc["project_id"] = project_oid
                _schedule_maintenance_start(
                    project_id=str(project_oid),
                    billing_plan=billing_plan,
                    stripe_subscription_id=_normalize(session.get("subscription")) or None,
                    stripe_customer_id=_normalize(session.get("customer")) or None,
                )
    if item_type == "package" and not manual_mode:
        _trigger_package_provisioning()

    return {
        "order_id": str(result.inserted_id),
        "existing": False,
        "type": event_type,
        "session_id": session_id,
        "email": email,
        "package_code": package_code,
        "item_type": item_type,
        "billing_plan": billing_plan,
        "project_id": str(order_doc["project_id"]) if order_doc.get("project_id") else None,
    }
