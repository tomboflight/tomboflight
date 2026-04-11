import re
from datetime import UTC, datetime, timedelta
from typing import Any, Optional, cast

import stripe
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.database import get_database
from app.services.billing_service import store_stripe_customer_reference
from app.services.project_service import (
    apply_package_purchase_to_project,
    create_project_from_paid_order,
)
from app.services.project_entitlement_service import update_project_entitlement_maintenance
from app.services.project_entitlement_service import MAINTENANCE_START_DELAY_DAYS


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
    normalized = _normalize(value).lower()

    mapping = {
        "legacy-snapshot": "legacy_snapshot",
        "legacy_snapshot": "legacy_snapshot",
        "legacy-portrait-intro": "legacy_portrait_intro",
        "legacy_portrait_intro": "legacy_portrait_intro",
        "digital-legacy-portrait": "digital_legacy_portrait",
        "digital_legacy_portrait": "digital_legacy_portrait",
        "starter-family-tree": "household_foundation",
        "starter_family_tree": "household_foundation",
        "household-foundation": "household_foundation",
        "household_foundation": "household_foundation",
        "heirloom-legacy-tree": "heirloom_legacy_tree",
        "heirloom_legacy_tree": "heirloom_legacy_tree",
        "legacy-plus": "legacy_plus",
        "legacy_plus": "legacy_plus",
        "family-estate-concierge": "family_estate_concierge",
        "family_estate_concierge": "family_estate_concierge",
        "command-structure-network": "command_structure_network",
        "command_structure_network": "command_structure_network",
        "extra-upload-pack": "extra_upload_pack",
        "extra_upload_pack": "extra_upload_pack",
        "extra-storage": "extra_storage",
        "extra_storage": "extra_storage",
        "portrait-polish": "portrait_polish",
        "portrait_polish": "portrait_polish",
        "tribute-narration": "tribute_narration",
        "tribute_narration": "tribute_narration",
        "extra-mapped-person": "extra_mapped_person",
        "extra_mapped_person": "extra_mapped_person",
        "extra-zoom-layer": "extra_zoom_layer",
        "extra_zoom_layer": "extra_zoom_layer",
        "additional-narration-minute": "additional_narration_minute",
        "additional_narration_minute": "additional_narration_minute",
        "on-site-photo-scanning": "on_site_photo_scanning",
        "on_site_photo_scanning": "on_site_photo_scanning",
        "extra-linked-household": "extra_linked_household",
        "extra_linked_household": "extra_linked_household",
        "extra-branch": "extra_branch",
        "extra_branch": "extra_branch",
        "white-glove-archive-support": "white_glove_archive_support",
        "white_glove_archive_support": "white_glove_archive_support",
        "extra-organization-node": "extra_org_node",
        "extra_org_node": "extra_org_node",
        "extra-organization-level": "extra_org_level",
        "extra_org_level": "extra_org_level",
        "extra-admin-seat": "extra_admin_seat",
        "extra_admin_seat": "extra_admin_seat",
        "command-report-add-on": "command_report_addon",
        "command_report_addon": "command_report_addon",
    }

    return mapping.get(normalized, normalized or "unknown")


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


def _to_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    normalized = _normalize(str(value or ""))
    if ObjectId.is_valid(normalized):
        return ObjectId(normalized)
    return None


def _project_is_approved(project: dict[str, Any]) -> bool:
    status_value = _normalize(project.get("status")).lower()
    phase_value = _normalize(project.get("phase")).lower()
    return status_value in APPROVED_PROJECT_STATUSES or phase_value in APPROVED_PROJECT_PHASES


def _find_matching_approved_project(*, user: dict[str, Any], email: str | None = None) -> Optional[dict[str, Any]]:
    db = cast(Database, get_database())
    projects = db.get_collection("projects")

    owner_email = _normalize_email(email or str(user.get("email") or ""))
    user_id_text = _normalize(str(user.get("_id") or user.get("id") or user.get("user_id") or ""))
    user_oid = _to_object_id(user_id_text)

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


def _link_order_to_project(
    *,
    orders: Collection,
    order_id: ObjectId,
    order_doc: dict[str, Any],
    project: dict[str, Any] | None,
) -> None:
    if not project:
        return
    project_oid = _to_object_id(project.get("_id") or project.get("id"))
    if project_oid is None:
        return
    orders.update_one(
        {"_id": order_id},
        {"$set": {"project_id": project_oid}},
    )
    order_doc["project_id"] = project_oid


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

    existing = orders.find_one(
        {
            "user_id": ObjectId(str(user["_id"])),
            "package_code": package_code,
            "status": payload.order_status,
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
        "status": payload.order_status,
        "stripe_session_id": payload.stripe_session_id,
        "stripe_payment_link_id": payload.stripe_payment_link_id,
        "project_id": None,
        "created_at": datetime.now(UTC),
    }

    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id

    if order_doc["item_type"] == "package":
        target_project_id = _normalize(getattr(payload, "project_id", None))
        if target_project_id:
            project = apply_package_purchase_to_project(
                user=user,
                project_id=target_project_id,
                package_code=package_code,
                package_name=payload.package_name,
                stripe_session_id=payload.stripe_session_id,
                stripe_payment_link_id=payload.stripe_payment_link_id,
            )
        else:
            project = _find_matching_approved_project(user=user)
            if project:
                project = apply_package_purchase_to_project(
                    user=user,
                    project_id=str(project.get("_id") or ""),
                    package_code=package_code,
                    package_name=payload.package_name,
                    stripe_session_id=payload.stripe_session_id,
                    stripe_payment_link_id=payload.stripe_payment_link_id,
                )
            else:
                project = create_project_from_paid_order(
                    user=user,
                    package_code=package_code,
                    package_name=payload.package_name,
                    stripe_session_id=payload.stripe_session_id,
                    stripe_payment_link_id=payload.stripe_payment_link_id,
                )
        _link_order_to_project(
            orders=orders,
            order_id=result.inserted_id,
            order_doc=order_doc,
            project=project,
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

    return _serialize_order(order_doc)


def get_orders_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    orders = _get_orders_collection()
    docs = list(
        orders.find({"user_id": ObjectId(str(user["_id"]))}).sort("created_at", -1)
    )
    return [_serialize_order(doc) for doc in docs]


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

    existing = orders.find_one({"stripe_session_id": session_id})
    if existing:
        return {
            "order_id": str(existing["_id"]),
            "existing": True,
            "type": event_type,
            "session_id": session_id,
        }

    item_type, package_code, package_name, price_label, billing_plan = _infer_purchase_fields(session)

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
        "project_id": None,
        "stripe_session_id": session_id,
        "stripe_payment_link_id": session.get("payment_link"),
        "created_at": datetime.now(UTC),
    }

    result = orders.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id

    if item_type == "package":
        target_project_id = _extract_target_project_id(session)
        if target_project_id:
            project = apply_package_purchase_to_project(
                user=user,
                project_id=target_project_id,
                package_code=package_code,
                package_name=package_name,
                stripe_session_id=session_id,
                stripe_payment_link_id=session.get("payment_link"),
            )
        else:
            project = _find_matching_approved_project(user=user, email=email)
            if project:
                project = apply_package_purchase_to_project(
                    user=user,
                    project_id=str(project.get("_id") or ""),
                    package_code=package_code,
                    package_name=package_name,
                    stripe_session_id=session_id,
                    stripe_payment_link_id=session.get("payment_link"),
                )
            else:
                project = create_project_from_paid_order(
                    user=user,
                    package_code=package_code,
                    package_name=package_name,
                    stripe_session_id=session_id,
                    stripe_payment_link_id=session.get("payment_link"),
                )
        _link_order_to_project(
            orders=orders,
            order_id=result.inserted_id,
            order_doc=order_doc,
            project=project,
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
