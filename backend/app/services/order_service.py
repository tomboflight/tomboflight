import re
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional, cast

import stripe
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.core.package_catalog import get_package
from app.core.package_mapping import normalize_package_code as normalize_mapped_package_code
from app.database import get_database
from app.services.auth_service import create_pending_checkout_user
from app.services.billing_service import store_stripe_customer_reference
from app.services.project_service import (
    apply_package_purchase_to_project,
    create_project_from_paid_order,
)
from app.services.project_entitlement_service import update_project_entitlement_maintenance
from app.services.project_entitlement_service import MAINTENANCE_START_DELAY_DAYS

AUTHORITATIVE_ORDER_SOURCES = {
    "stripe_webhook",
    "stripe_verified",
    "admin_manual",
}

PAID_ORDER_STATUSES = {"paid", "complete", "completed", "succeeded"}
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
    orders.update_one(
        {"_id": order_id},
        {"$set": {"project_id": project_oid}},
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
        "package_name": order.get("package_name", ""),
        "price_label": order.get("price_label", ""),
        "item_type": order.get("item_type", "package"),
        "billing_plan": order.get("billing_plan", "one_time"),
        "source": order.get("source", "stripe"),
        "status": order.get("status", "paid"),
        "project_id": str(order["project_id"]) if order.get("project_id") else None,
        "stripe_session_id": order.get("stripe_session_id"),
        "stripe_payment_link_id": order.get("stripe_payment_link_id"),
        "created_at": order["created_at"],
    }


def create_order_for_user(user: dict[str, Any], payload: Any) -> dict[str, Any]:
    orders = _get_orders_collection()

    package_code = _normalize_package_code(
        getattr(payload, "package_code", None) or getattr(payload, "package_slug", None)
    )
    order_status = _public_checkout_status(
        getattr(payload, "source", ""),
        getattr(payload, "order_status", ""),
    )
    stripe_session_id = _normalize(getattr(payload, "stripe_session_id", None))

    existing = None
    if stripe_session_id:
        existing = orders.find_one({"stripe_session_id": stripe_session_id})

    if existing is None:
        existing = orders.find_one(
            {
                "user_id": ObjectId(str(user["_id"])),
                "package_code": package_code,
                "status": order_status,
            },
            sort=[("created_at", -1)],
        )

    if existing:
        return _serialize_order(existing)

    order_doc = {
        "user_id": ObjectId(str(user["_id"])),
        "email": user["email"],
        "package_code": package_code,
        "package_slug": package_code,
        "package_name": payload.package_name,
        "price_label": payload.price_label,
        "item_type": getattr(payload, "item_type", "package"),
        "billing_plan": getattr(payload, "billing_plan", "one_time"),
        "source": payload.source,
        "status": order_status,
        "created_at": datetime.now(UTC),
    }
    _set_if_present(order_doc, "stripe_session_id", payload.stripe_session_id)
    _set_if_present(order_doc, "stripe_payment_link_id", payload.stripe_payment_link_id)

    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id

    if (
        order_doc["item_type"] == "package"
        and order_doc["status"] in PAID_ORDER_STATUSES
        and _is_authoritative_order_source(order_doc.get("source"))
    ):
        target_project_id = _normalize(getattr(payload, "project_id", None))
        order_doc = _attach_project_to_paid_package_order(
            order_id=result.inserted_id,
            order_doc=order_doc,
            user=user,
            package_code=package_code,
            package_name=payload.package_name,
            target_project_id=target_project_id,
            stripe_session_id=payload.stripe_session_id,
            stripe_payment_link_id=payload.stripe_payment_link_id,
        )
    elif order_doc["item_type"] == "maintenance":
        target_project_id = _normalize(getattr(payload, "project_id", None))
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
                    billing_plan=order_doc.get("billing_plan", "monthly"),
                )

    if order_doc["item_type"] == "package":
        _trigger_package_provisioning()

    return _serialize_order(order_doc)


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
            return

    _ensure_index([("user_id", 1)], name="user_id_1")
    _ensure_index([("email", 1)], name="email_1")
    _ensure_index([("package_code", 1)], name="package_code_1")
    _ensure_index([("package_slug", 1)], name="package_slug_1")
    _ensure_index([("item_type", 1)], name="item_type_1")
    _ensure_index([("billing_plan", 1)], name="billing_plan_1")
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


def _format_price_label(amount_subtotal: Any, billing_plan: str) -> str:
    if not isinstance(amount_subtotal, int):
        return "paid"

    amount = amount_subtotal / 100

    if billing_plan == "monthly":
        return f"${amount:,.2f}/month"
    if billing_plan == "yearly":
        return f"${amount:,.2f}/year"

    return f"${amount:,.2f}"


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
    return _normalize(
        metadata.get("project_id")
        or metadata.get("upgrade_project_id")
        or metadata.get("existing_project_id")
        or metadata.get("target_project_id")
    )


def _infer_purchase_fields(session: dict[str, Any]) -> tuple[str, str, str, str, str]:
    metadata = session.get("metadata") or {}

    raw_code = (
        metadata.get("package_code")
        or metadata.get("package_slug")
        or metadata.get("package")
    )
    package_name = _normalize(metadata.get("package_name"))
    price_label = _normalize(metadata.get("price_label"))
    item_type = _normalize(metadata.get("item_type") or metadata.get("type")) or "package"
    billing_plan = _normalize(metadata.get("billing_plan")) or _extract_billing_plan_from_session(session)

    if raw_code:
        package_code = _normalize_package_code(raw_code)
        if package_name and price_label:
            return item_type, package_code, package_name, price_label, billing_plan

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
        user = create_pending_checkout_user(
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

    orders = _get_orders_collection()

    item_type, package_code, package_name, price_label, billing_plan = _infer_purchase_fields(session)
    stripe_payment_link_id = session.get("payment_link")

    existing = orders.find_one({"stripe_session_id": session_id})
    if existing:
        update_fields: dict[str, Any] = {
            "email": email,
            "package_code": package_code,
            "package_slug": package_code,
            "package_name": package_name,
            "price_label": price_label,
            "item_type": item_type,
            "billing_plan": billing_plan,
            "source": "stripe_webhook",
            "status": "paid",
            "stripe_session_id": session_id,
        }
        _set_if_present(update_fields, "stripe_payment_link_id", stripe_payment_link_id)
        orders.update_one({"_id": existing["_id"]}, {"$set": update_fields})

        order_doc = orders.find_one({"_id": existing["_id"]}) or {
            **existing,
            **update_fields,
        }
        if item_type == "package" and not order_doc.get("project_id"):
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
        if item_type == "package":
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
        "package_name": package_name,
        "price_label": price_label,
        "item_type": item_type,
        "billing_plan": billing_plan,
        "source": "stripe_webhook",
        "status": "paid",
        "stripe_session_id": session_id,
        "created_at": datetime.now(UTC),
    }
    _set_if_present(order_doc, "stripe_payment_link_id", stripe_payment_link_id)

    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id

    if item_type == "package":
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
    if item_type == "package":
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
