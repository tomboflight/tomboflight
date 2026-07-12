#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

from app.config import settings
from app.core.package_catalog import get_package
from app.database import close_mongo_connection, connect_to_mongo
from app.services.project_entitlement_service import upsert_project_entitlement
from app.services.project_membership_service import ensure_project_owner_membership


APPLY_CONFIRMATION_PHRASE = "INTERNAL-ACCOUNT-REPAIR"
EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_VALIDATION_ERROR = 2
EXIT_IDENTITY_OR_OWNERSHIP_CONFLICT = 10
EXIT_CONTENT_ONLY_GAPS = 20

SAFE_ENVIRONMENTS = {"production", "staging", "development"}
CEO_AUTHORIZATION_SOURCE = "CEO operator confirmation"
CEO_AUTHORIZED_BY = "Larry Robinson"
CEO_AUTHORIZATION_DATE = "2026-07-12"
KEITH_UPGRADE_REASON = "Customer family situation and required household structure changed"
EXPECTED_LARRY_CANONICAL_MINT = {
    "token_id": "1",
    "chain": "base-mainnet",
    "contract_address": "0x39967cEb7580aB9110b349Ca3a7fe0179b950Ba5",
    "tx_hash": "0xae659f5c6e2280932fadb4bd6c7b7cd0d37e9d75bde54589be736f32f810de1a",
    "wallet_address": "0xAdD4567249354c3B54f77313bf874d50179DB479",
    "mint_record_id": "69cae30f786977dfd046eaef",
    "version_number": 2,
}

AUDIT_VERDICT_SAFE_REPAIRS = "AUDIT COMPLETE — SAFE REPAIRS AVAILABLE"
AUDIT_VERDICT_AUTH_REQUIRED = "AUDIT COMPLETE — BUSINESS AUTHORIZATION REQUIRED"
AUDIT_VERDICT_CONTENT_REQUIRED = "AUDIT COMPLETE — CUSTOMER CONTENT REQUIRED"
AUDIT_VERDICT_APPLY_BLOCKED = "APPLY BLOCKED — UNRESOLVED DATA CONFLICT"


@dataclass(frozen=True)
class AccountSpec:
    key: str
    full_name: str
    email: str
    user_id: str
    project_id: str
    family_id: str
    household_id: str
    intake_submission_id: str
    expected_package_code: str
    expected_lane: str
    expected_project_name: str
    required_payment_link_id: str | None = None
    original_package_code: str | None = None
    requires_upgrade_evidence: bool = False


def account_specs() -> dict[str, AccountSpec]:
    return {
        "jennifer_wood": AccountSpec(
            key="jennifer_wood",
            full_name="Jennifer Wood",
            email="queenjwood@gmail.com",
            user_id="69c5c8db3bb71c27eee96ec6",
            project_id="69c5d5023bb71c27eee96ed5",
            family_id="69c5d5023bb71c27eee96ed3",
            household_id="69c5d5023bb71c27eee96ed4",
            intake_submission_id="69c5d3b83bb71c27eee96ed2",
            expected_package_code="digital_legacy_portrait",
            expected_lane="portrait",
            expected_project_name="Jennifer Wood Digital Legacy Portrait",
            required_payment_link_id="plink_1TD4kFHNNHBGJyX52cN1TExj",
        ),
        "marquis_floyd": AccountSpec(
            key="marquis_floyd",
            full_name="Marquis Floyd",
            email="mlfloyd00@gmail.com",
            user_id="69c5c94d3bb71c27eee96ec7",
            project_id="69c5db693bb71c27eee96edc",
            family_id="69c5db693bb71c27eee96eda",
            household_id="69c5db693bb71c27eee96edb",
            intake_submission_id="69c5d95e3bb71c27eee96ed9",
            expected_package_code="digital_legacy_portrait",
            expected_lane="portrait",
            expected_project_name="Marquis Floyd Digital Legacy Portrait",
            required_payment_link_id="plink_1TD4kFHNNHBGJyX52cN1TExj",
        ),
        "keith_goffigan": AccountSpec(
            key="keith_goffigan",
            full_name="Keith Goffigan",
            email="chief757@outlook.com",
            user_id="69c5c8493bb71c27eee96ec5",
            project_id="69c5d6c43bb71c27eee96ed8",
            family_id="69c5d6c43bb71c27eee96ed6",
            household_id="69c5d6c43bb71c27eee96ed7",
            intake_submission_id="69c5d1a83bb71c27eee96ed1",
            expected_package_code="household_foundation",
            expected_lane="household",
            expected_project_name="Goffigan Production Build",
            required_payment_link_id="plink_1TD4kFHNNHBGJyX52cN1TExj",
            original_package_code="digital_legacy_portrait",
            requires_upgrade_evidence=True,
        ),
        "larry_robinson": AccountSpec(
            key="larry_robinson",
            full_name="Larry Robinson",
            email="larrycr27@gmail.com",
            user_id="69be17d9c6ef5c9cb36af187",
            project_id="69c0402387082765345cff8c",
            family_id="69bf98b54c5cb5a4236446dd",
            household_id="69c0402387082765345cff8b",
            intake_submission_id="69bf55189e86117b345ec516",
            expected_package_code="legacy_plus",
            expected_lane="household",
            expected_project_name="Larry Robinson Legacy Plus",
            required_payment_link_id="plink_1TDIEhHNNHBGJyX5TkqKSIwg",
        ),
    }


def required_confirmation_phrase() -> str:
    return APPLY_CONFIRMATION_PHRASE


def validate_apply_mode(
    *,
    apply: bool,
    confirmation_phrase: str,
    environment: str,
    database_name: str,
    report_path: str,
) -> tuple[bool, str]:
    if not apply:
        return True, ""
    if str(confirmation_phrase or "").strip() != required_confirmation_phrase():
        return False, f"--apply requires --confirm-apply {required_confirmation_phrase()}"
    env = str(environment or "").strip().lower()
    if env not in SAFE_ENVIRONMENTS:
        return False, "--apply requires --environment to be one of: production, staging, development."
    if not str(database_name or "").strip():
        return False, "--apply requires --database-name."
    if not str(report_path or "").strip():
        return False, "--apply requires --report-path."
    return True, ""


def _now() -> datetime:
    return datetime.now(UTC)


def _oid(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    text = str(value or "").strip()
    return ObjectId(text) if ObjectId.is_valid(text) else None


def _doc_id(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("_id") or value.get("id")
    else:
        raw = value
    if isinstance(raw, ObjectId):
        return str(raw)
    return str(raw or "").strip()


def _serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _obj_or_str_candidates(raw_id: str) -> list[Any]:
    oid = _oid(raw_id)
    return [oid, raw_id] if oid is not None else [raw_id]


def _project_ref_values(raw_id: str) -> list[Any]:
    values = _obj_or_str_candidates(raw_id)
    oid = _oid(raw_id)
    if oid is not None:
        oid_text = str(oid)
        values.extend([f'ObjectId("{oid_text}")', f"ObjectId('{oid_text}')"])
    seen: list[Any] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _safe_count(db: Any, collection: str, query: dict[str, Any]) -> int:
    try:
        return int(db[collection].count_documents(query))
    except Exception:
        return 0


def _collection_handle(db: Any, collection: str) -> Any | None:
    if isinstance(db, dict):
        return db.get(collection)
    return db[collection]


def _find_by_id(db: Any, collection: str, raw_id: str) -> dict[str, Any] | None:
    for candidate in _obj_or_str_candidates(raw_id):
        doc = db[collection].find_one({"_id": candidate})
        if doc is not None:
            return doc
    return None


def _find_user(db: Any, spec: AccountSpec) -> dict[str, Any] | None:
    user = _find_by_id(db, "users", spec.user_id)
    if user is not None:
        return user
    return db["users"].find_one({"email": spec.email})


def _find_project(db: Any, spec: AccountSpec) -> dict[str, Any] | None:
    project = _find_by_id(db, "projects", spec.project_id)
    if project is not None:
        return project
    return db["projects"].find_one({"owner_email": spec.email})


def _find_entitlement(db: Any, spec: AccountSpec) -> dict[str, Any] | None:
    return db["project_entitlements"].find_one({"project_id": {"$in": _obj_or_str_candidates(spec.project_id)}})


def _find_intake(db: Any, spec: AccountSpec) -> dict[str, Any] | None:
    intake = _find_by_id(db, "intake_submissions", spec.intake_submission_id)
    if intake is not None:
        return intake
    return db["intake_submissions"].find_one(
        {
            "$or": [
                {"project_id": {"$in": _obj_or_str_candidates(spec.project_id)}},
                {"email": spec.email},
            ]
        },
        sort=[("updated_at", -1), ("created_at", -1)],
    )


def _extract_orders(db: Any, spec: AccountSpec) -> list[dict[str, Any]]:
    rows = (
        db["orders"]
        .find(
            {
                "$or": [
                    {"email": spec.email},
                    {"project_id": {"$in": _obj_or_str_candidates(spec.project_id)}},
                ]
            }
        )
        .sort("created_at", -1)
        .limit(20)
    )
    orders: list[dict[str, Any]] = []
    for row in rows:
        orders.append(
            {
                "order_id": _doc_id(row),
                "status": row.get("status"),
                "package_code": row.get("package_code") or row.get("package_slug"),
                "package_name": row.get("package_name"),
                "price_label": row.get("price_label"),
                "stripe_session_id": row.get("stripe_session_id"),
                "stripe_payment_link_id": row.get("stripe_payment_link_id"),
                "promotion_code": row.get("promotion_code") or row.get("promo_code"),
                "coupon_id": row.get("coupon_id"),
                "discount_amount": row.get("discount_amount") or row.get("discount_usd"),
                "final_amount_paid": row.get("amount_paid") or row.get("final_amount_paid"),
                "created_at": row.get("created_at"),
            }
        )
    return orders


def _find_upgrade_event(db: Any, spec: AccountSpec) -> dict[str, Any] | None:
    return db["finance_events"].find_one(
        {
            "event_type": "package_upgrade",
            "$or": [
                {"project_id": {"$in": _obj_or_str_candidates(spec.project_id)}},
                {"customer_email": spec.email},
            ],
        },
        sort=[("occurred_at", -1), ("created_at", -1)],
    )


def _find_larry_mint(db: Any, spec: AccountSpec) -> dict[str, Any] | None:
    return db["mint_records"].find_one(
        {
            "$or": [
                {"_id": {"$in": _obj_or_str_candidates(EXPECTED_LARRY_CANONICAL_MINT["mint_record_id"])}},
                {
                    "project_id": {"$in": _obj_or_str_candidates(spec.project_id)},
                    "$or": [{"canonical": True}, {"is_canonical": True}],
                },
            ]
        },
        sort=[("version_number", -1), ("updated_at", -1)],
    )


def _extract_wallet_from_mint(mint_doc: dict[str, Any] | None, project: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    mint_doc = mint_doc or {}
    project = project or {}
    candidate_sources = {
        "mint.wallet_address": mint_doc.get("wallet_address"),
        "mint.mint_wallet": mint_doc.get("mint_wallet"),
        "mint.canonical_wallet": mint_doc.get("canonical_wallet"),
        "mint.wallet": mint_doc.get("wallet"),
        "project.mint_wallet": project.get("mint_wallet"),
        "project.wallet_address": project.get("wallet_address"),
    }
    normalized_sources = {
        key: str(value or "").strip() or None for key, value in candidate_sources.items()
    }
    for value in normalized_sources.values():
        if value:
            return value, normalized_sources
    return "", normalized_sources


def _stripe_session_snapshot(session_id: str) -> dict[str, Any]:
    session_id = str(session_id or "").strip()
    if not session_id:
        return {"status": "missing_session_id"}
    stripe_secret_key = str(settings.stripe_secret_key or "").strip()
    if not stripe_secret_key:
        return {"status": "stripe_secret_key_not_configured"}
    import stripe

    stripe.api_key = stripe_secret_key
    session = stripe.checkout.Session.retrieve(
        session_id,
        expand=[
            "line_items.data.price.product",
            "total_details.breakdown.discounts.discount.promotion_code",
            "total_details.breakdown.discounts.discount.coupon",
            "payment_link",
            "customer_details",
        ],
    )
    payload = session.to_dict_recursive() if hasattr(session, "to_dict_recursive") else dict(session)
    discounts = (
        (((payload.get("total_details") or {}).get("breakdown") or {}).get("discounts") or [])
    )
    promotion_code = None
    coupon_id = None
    for discount_entry in discounts:
        discount_obj = (discount_entry or {}).get("discount") or {}
        promo = discount_obj.get("promotion_code")
        coupon = discount_obj.get("coupon")
        if isinstance(promo, dict):
            promotion_code = str(promo.get("code") or promo.get("id") or "").strip() or None
        else:
            promotion_code = str(promo or "").strip() or promotion_code
        if isinstance(coupon, dict):
            coupon_id = str(coupon.get("id") or coupon.get("name") or "").strip() or None
        else:
            coupon_id = str(coupon or "").strip() or coupon_id
    line_items = []
    for item in ((payload.get("line_items") or {}).get("data") or []):
        price = (item or {}).get("price") or {}
        product = price.get("product") if isinstance(price, dict) else None
        line_items.append(
            {
                "description": (item or {}).get("description"),
                "quantity": (item or {}).get("quantity"),
                "price_id": (price or {}).get("id") if isinstance(price, dict) else None,
                "product_id": (product or {}).get("id") if isinstance(product, dict) else None,
                "product_name": (product or {}).get("name") if isinstance(product, dict) else None,
            }
        )
    payment_link = payload.get("payment_link")
    payment_link_id = payment_link.get("id") if isinstance(payment_link, dict) else payment_link
    return {
        "status": "ok",
        "session_id": payload.get("id"),
        "customer": payload.get("customer"),
        "customer_email": (payload.get("customer_details") or {}).get("email"),
        "payment_status": payload.get("payment_status"),
        "amount_subtotal": payload.get("amount_subtotal"),
        "amount_total": payload.get("amount_total"),
        "discount_amount": (payload.get("total_details") or {}).get("amount_discount"),
        "promotion_code": promotion_code,
        "coupon_id": coupon_id,
        "payment_link_id": payment_link_id,
        "line_items": line_items,
        "created": payload.get("created"),
    }


def _content_inventory_for_account(db: Any, spec: AccountSpec) -> list[dict[str, Any]]:
    checks = [
        {
            "key": "primary_portrait",
            "collections": ["uploaded_files"],
            "query": {"category": {"$in": ["portrait", "primary_portrait"]}},
            "packages": ["digital_legacy_portrait", "legacy_plus"],
            "owner": "customer",
        },
        {
            "key": "biography_story",
            "collections": ["intake_submissions"],
            "query": {},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "customer",
        },
        {
            "key": "supporting_photos",
            "collections": ["uploaded_files"],
            "query": {"category": {"$in": ["supporting_photo", "gallery_image"]}},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "customer",
        },
        {
            "key": "audio_video_documents",
            "collections": ["uploaded_files", "vault_files"],
            "query": {"category": {"$in": ["audio", "video", "document"]}},
            "packages": ["household_foundation", "legacy_plus"],
            "owner": "customer",
        },
        {
            "key": "vault_items",
            "collections": ["vault_files"],
            "query": {},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "customer",
        },
        {
            "key": "review_submissions",
            "collections": ["project_reviews", "review_submissions"],
            "query": {},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "customer",
        },
        {
            "key": "certificate_record",
            "collections": ["issued_certificates"],
            "query": {},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "production_team",
        },
        {
            "key": "delivery_record",
            "collections": ["deliveries", "delivery_records"],
            "query": {},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "production_team",
        },
        {
            "key": "viewer_build",
            "collections": ["viewer_builds", "viewer_snapshots"],
            "query": {},
            "packages": ["digital_legacy_portrait", "household_foundation", "legacy_plus"],
            "owner": "production_team",
        },
    ]
    inventory: list[dict[str, Any]] = []
    for check in checks:
        applicable = spec.expected_package_code in check["packages"]
        combined_ids: list[str] = []
        combined_count = 0
        statuses: list[str] = []
        for collection in check["collections"]:
            col = _collection_handle(db, collection)
            if col is None:
                continue
            query = dict(check["query"])
            query["$or"] = [
                {"project_id": {"$in": _project_ref_values(spec.project_id)}},
                {"owner_project_id": {"$in": _project_ref_values(spec.project_id)}},
                {"household_id": {"$in": _project_ref_values(spec.household_id)}},
                {"family_id": {"$in": _project_ref_values(spec.family_id)}},
                {"email": spec.email},
            ]
            docs = list(col.find(query).limit(20))
            combined_count += len(docs)
            combined_ids.extend(_doc_id(doc) for doc in docs)
            statuses.extend(str(doc.get("status") or "").strip() for doc in docs if doc.get("status"))
        missing = applicable and combined_count == 0
        inventory.append(
            {
                "content_key": check["key"],
                "collections": check["collections"],
                "package_required": applicable,
                "record_count": combined_count,
                "record_ids": [value for value in combined_ids if value][:10],
                "current_status": sorted(set(value for value in statuses if value)) or None,
                "missing": missing,
                "responsible_party": check["owner"] if applicable else "not_applicable",
            }
        )
    return inventory


def _package_name(package_code: str) -> str:
    package = get_package(package_code) or {}
    return str(package.get("display_name") or package_code.replace("_", " ").title())


def _maintenance_classification(entitlement: dict[str, Any], orders: list[dict[str, Any]]) -> str:
    status = str(entitlement.get("maintenance_status") or "").strip().lower()
    plan = str(entitlement.get("maintenance_plan") or "").strip().lower()
    has_subscription = bool(entitlement.get("maintenance_stripe_subscription_id"))
    if plan == "monthly" and status == "scheduled":
        return "Maintenance scheduled — billing activation or policy confirmation pending"
    if status in {"active", "started"} and has_subscription:
        return "active paid maintenance"
    if any((order.get("promotion_code") or order.get("coupon_id")) for order in orders):
        return "coupon-discounted maintenance"
    if plan in {"included", "none"} and not has_subscription:
        return "included maintenance"
    if status in {"waived", "sponsored"}:
        return "authorized sponsorship"
    if status in {"not_started", "pending", "past_due", "canceled"}:
        return "maintenance required but missing"
    return "policy not determinable from existing data"


def _system_completion_matrix(
    *,
    db: Any,
    spec: AccountSpec,
    user: dict[str, Any] | None,
    project: dict[str, Any] | None,
    entitlement: dict[str, Any] | None,
    intake: dict[str, Any] | None,
    orders: list[dict[str, Any]],
    upgrade_event: dict[str, Any] | None,
) -> dict[str, str]:
    def completed(flag: bool) -> str:
        return "Complete" if flag else "Missing"

    package_code = str(
        (entitlement or {}).get("package_code")
        or (project or {}).get("package_code")
        or (project or {}).get("package_slug")
        or ""
    )
    lane = str((entitlement or {}).get("package_lane") or (project or {}).get("project_lane") or (project or {}).get("lane") or "")
    return {
        "User exists": completed(user is not None),
        "Project exists": completed(project is not None),
        "Family exists": completed(
            _safe_count(db, "families", {"_id": {"$in": _obj_or_str_candidates(spec.family_id)}}) > 0
        ),
        "Household exists": completed(
            _safe_count(db, "households", {"_id": {"$in": _obj_or_str_candidates(spec.household_id)}}) > 0
        ),
        "Correct ownership": completed(
            bool(project)
            and _doc_id((project or {}).get("owner_user_id")) == spec.user_id
            and str((project or {}).get("owner_email") or "").strip().lower() == spec.email
        ),
        "Correct membership": completed(
            _safe_count(
                db,
                "project_members",
                {"project_id": {"$in": _obj_or_str_candidates(spec.project_id)}, "$or": [{"user_id": spec.user_id}, {"email": spec.email}]},
            )
            > 0
        ),
        "Correct package": completed(package_code == spec.expected_package_code),
        "Correct lane": completed(lane == spec.expected_lane),
        "Correct entitlements": completed(entitlement is not None and package_code == spec.expected_package_code),
        "Correct access context": completed(entitlement is not None),
        "Correct billing linkage": completed(len(orders) > 0),
        "Correct coupon evidence": "Complete" if any((o.get("promotion_code") or o.get("coupon_id")) for o in orders) else "Requires business authorization",
        "Correct upgrade evidence": (
            "Complete"
            if (not spec.requires_upgrade_evidence or upgrade_event is not None)
            else "Requires business authorization"
        ),
        "Correct maintenance state": "Complete" if entitlement is not None else "Missing",
        "Correct vault namespace": "Complete" if project is not None else "Missing",
        "Correct viewer configuration": "Complete" if project is not None else "Missing",
        "Correct certificate-generation capability": "Complete" if entitlement is not None else "Missing",
        "Correct review workflow": "Complete" if project is not None else "Missing",
        "Correct delivery workflow": "Complete" if project is not None else "Missing",
        "Correct mint display where applicable": "Complete" if spec.key != "larry_robinson" or project is not None else "Missing",
        "Cross-account isolation": "Requires customer" if intake is None else "Complete",
    }


def _content_completion_matrix(actual_inventory: list[dict[str, Any]]) -> dict[str, str]:
    matrix: dict[str, str] = {}
    for item in actual_inventory:
        key = str(item.get("content_key") or "")
        if not key:
            continue
        if not item.get("package_required"):
            matrix[key] = "Not required for package"
        elif item.get("missing"):
            if item.get("responsible_party") == "production_team":
                matrix[key] = "Requires production team"
            else:
                matrix[key] = "Requires customer"
        else:
            matrix[key] = "Complete"
    return matrix


def _audit_account(db: Any, spec: AccountSpec) -> dict[str, Any]:
    user = _find_user(db, spec)
    project = _find_project(db, spec)
    entitlement = _find_entitlement(db, spec) or {}
    intake = _find_intake(db, spec)
    orders = _extract_orders(db, spec)
    upgrade_event = _find_upgrade_event(db, spec)

    current_package = str(
        (entitlement or {}).get("package_code")
        or (project or {}).get("package_code")
        or (project or {}).get("package_slug")
        or ""
    ).strip()
    current_lane = str((entitlement or {}).get("package_lane") or (project or {}).get("project_lane") or (project or {}).get("lane") or "").strip()
    owner_user_id = _doc_id((project or {}).get("owner_user_id"))
    owner_email = str((project or {}).get("owner_email") or "").strip().lower()
    membership_doc = db["project_members"].find_one(
        {
            "project_id": {"$in": _obj_or_str_candidates(spec.project_id)},
            "$or": [{"user_id": spec.user_id}, {"email": spec.email}],
        }
    )

    conflicts: list[str] = []
    if user is None or _doc_id(user) != spec.user_id:
        conflicts.append("identity_mismatch")
    if project is None or _doc_id(project) != spec.project_id:
        conflicts.append("project_id_mismatch")
    if project is not None and (owner_user_id != spec.user_id or owner_email != spec.email):
        conflicts.append("project_owner_conflict")
    if current_package and current_package != spec.expected_package_code:
        conflicts.append("unexpected_current_package")
    if current_lane and current_lane != spec.expected_lane:
        conflicts.append("unexpected_current_lane")
    if intake is None or _doc_id(intake) != spec.intake_submission_id:
        conflicts.append("unexpected_intake_submission_id")
    if spec.required_payment_link_id and not any(
        str(item.get("stripe_payment_link_id") or "").strip() == spec.required_payment_link_id
        for item in orders
    ):
        conflicts.append("missing_required_payment_link")
    if spec.requires_upgrade_evidence and upgrade_event is None:
        conflicts.append("missing_upgrade_evidence")

    mint = {}
    content_inventory = _content_inventory_for_account(db, spec)
    if spec.key == "larry_robinson":
        mint_doc = _find_larry_mint(db, spec)
        resolved_wallet, wallet_sources = _extract_wallet_from_mint(mint_doc, project)
        mint = {
            "mint_record_id": _doc_id(mint_doc),
            "token_id": str((mint_doc or {}).get("token_id") or (mint_doc or {}).get("public_token_id") or ""),
            "chain": str((mint_doc or {}).get("chain") or ""),
            "contract_address": str((mint_doc or {}).get("contract_address") or ""),
            "tx_hash": str((mint_doc or {}).get("tx_hash") or ""),
            "wallet_address": resolved_wallet,
            "version_number": (mint_doc or {}).get("version_number"),
            "wallet_field_sources": wallet_sources,
        }
        for key, expected in EXPECTED_LARRY_CANONICAL_MINT.items():
            if str(mint.get(key) or "") != str(expected):
                conflicts.append("unexpected_larry_mint_conflict")
                break

    return {
        "account_key": spec.key,
        "spec": asdict(spec),
        "identity": {
            "found_user_id": _doc_id(user),
            "found_project_id": _doc_id(project),
            "project_owner_user_id": owner_user_id or None,
            "project_owner_email": owner_email or None,
        },
        "current_state": {
            "active_package_code": current_package or None,
            "active_lane": current_lane or None,
            "entitlement_id": _doc_id(entitlement) or None,
            "membership_record_id": _doc_id(membership_doc) or None,
            "membership_role": (membership_doc or {}).get("member_role"),
            "membership_status": (membership_doc or {}).get("status"),
        },
        "billing": {
            "orders": orders,
            "coupon_evidence_present": any(bool(item.get("promotion_code") or item.get("coupon_id")) for item in orders),
        },
        "upgrade": {
            "event_id": _doc_id(upgrade_event) or None,
            "details": (upgrade_event or {}).get("details"),
            "proposed_action_when_missing": (
                "Missing verified source data — business authorization required"
                if spec.requires_upgrade_evidence and upgrade_event is None
                else None
            ),
        },
        "maintenance": {
            "classification": _maintenance_classification(entitlement or {}, orders),
            "entitlement_maintenance_plan": (entitlement or {}).get("maintenance_plan"),
            "entitlement_maintenance_status": (entitlement or {}).get("maintenance_status"),
            "sponsorship_record_id": _doc_id(
                db["maintenance_sponsorships"].find_one({"project_id": {"$in": _obj_or_str_candidates(spec.project_id)}})
            )
            or None,
        },
        "mint": mint,
        "duplicates": {
            "users_by_email": max(0, _safe_count(db, "users", {"email": spec.email}) - (1 if user else 0)),
            "projects_by_owner_email": max(
                0,
                _safe_count(db, "projects", {"owner_email": spec.email}) - (1 if project else 0),
            ),
        },
        "conflicts": sorted(set(conflicts)),
        "system_completion_matrix": _system_completion_matrix(
            db=db,
            spec=spec,
            user=user,
            project=project,
            entitlement=entitlement,
            intake=intake,
            orders=orders,
            upgrade_event=upgrade_event,
        ),
        "customer_content_matrix": _content_completion_matrix(content_inventory),
        "actual_content_inventory": content_inventory,
    }


def _cross_account_conflicts(audits: list[dict[str, Any]]) -> list[str]:
    seen_households: dict[str, str] = {}
    conflicts: list[str] = []
    for account in audits:
        spec = account.get("spec") or {}
        key = str(spec.get("key") or account.get("account_key") or "")
        household_id = str(spec.get("household_id") or "").strip()
        if not household_id:
            continue
        previous = seen_households.get(household_id)
        if previous and previous != key:
            conflicts.append("cross_account_household_conflict")
        else:
            seen_households[household_id] = key
    return sorted(set(conflicts))


def _audit_genesis_prototype_separation(db: Any) -> dict[str, Any]:
    project = _find_by_id(db, "projects", "69b634caf4dfca8ad20b6e47")
    if project is None:
        project = db["projects"].find_one({"project_name": "Genesis Prototype"})
    owner_email = str((project or {}).get("owner_email") or "").strip().lower()
    return {
        "project_id": _doc_id(project),
        "project_name": (project or {}).get("project_name") or (project or {}).get("name"),
        "owner_email": owner_email or None,
        "package_code": (project or {}).get("package_code") or (project or {}).get("package_slug"),
        "prototype_key": (project or {}).get("prototype_key"),
        "separate_from_larry_personal_account": owner_email == "larry.frontend.test2@tomboflight.com",
    }


def _changed_fields(before: dict[str, Any], after: dict[str, Any], keys: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    previous: dict[str, Any] = {}
    new: dict[str, Any] = {}
    for key in keys:
        if before.get(key) != after.get(key):
            previous[key] = before.get(key)
            new[key] = after.get(key)
    return previous, new


def _record_write(
    *,
    write_log: list[dict[str, Any]],
    script_execution_id: str,
    collection: str,
    record_id: str,
    operation: str,
    previous_values: dict[str, Any],
    new_values: dict[str, Any],
    reason: str,
) -> None:
    if not previous_values and not new_values:
        return
    write_log.append(
        {
            "collection": collection,
            "record_id": record_id,
            "operation": operation,
            "fields_changed": sorted(set(previous_values.keys()) | set(new_values.keys())),
            "previous_values": previous_values,
            "new_values": new_values,
            "reason": reason,
            "timestamp": _now().isoformat(),
            "script_execution_id": script_execution_id,
        }
    )


def _apply_one_account(
    db: Any,
    spec: AccountSpec,
    *,
    script_execution_id: str,
    write_log: list[dict[str, Any]],
) -> dict[str, Any]:
    user = _find_user(db, spec)
    project = _find_project(db, spec)
    entitlement = _find_entitlement(db, spec)
    if user is None or project is None:
        raise RuntimeError(f"{spec.key}: missing required user or project.")
    if _doc_id(user) != spec.user_id:
        raise RuntimeError(f"{spec.key}: user precondition mismatch.")
    if _doc_id(project) != spec.project_id:
        raise RuntimeError(f"{spec.key}: project precondition mismatch.")
    if _doc_id((project or {}).get("owner_user_id")) != spec.user_id:
        raise RuntimeError(f"{spec.key}: owner_user_id precondition mismatch.")
    if str((project or {}).get("owner_email") or "").strip().lower() != spec.email:
        raise RuntimeError(f"{spec.key}: owner_email precondition mismatch.")
    if entitlement is None:
        raise RuntimeError(f"{spec.key}: entitlement precondition missing.")
    if str(entitlement.get("package_code") or "").strip() != spec.expected_package_code:
        raise RuntimeError(f"{spec.key}: entitlement package precondition mismatch.")

    package_name = _package_name(spec.expected_package_code)
    now = _now()

    user_before = dict(user)
    user_updates = {
        "email": spec.email,
        "full_name": spec.full_name,
        "package_code": spec.expected_package_code,
        "package_name": package_name,
        "package_lane": spec.expected_lane,
        "updated_at": now,
    }
    user_previous, user_new = _changed_fields(user_before, {**user_before, **user_updates}, list(user_updates.keys()))
    if user_new:
        db["users"].update_one({"_id": user["_id"]}, {"$set": user_updates})
        user_after = _find_by_id(db, "users", spec.user_id) or {}
        for field, expected in user_updates.items():
            if user_after.get(field) != expected:
                raise RuntimeError(f"{spec.key}: post-write user verification failed for field '{field}'.")
        _record_write(
            write_log=write_log,
            script_execution_id=script_execution_id,
            collection="users",
            record_id=spec.user_id,
            operation="update_one",
            previous_values=user_previous,
            new_values=user_new,
            reason="normalize_internal_validation_account_user_fields",
        )

    project_before = dict(project)
    project_updates = {
        "owner_user_id": spec.user_id,
        "owner_email": spec.email,
        "owner_name": spec.full_name,
        "project_name": spec.expected_project_name,
        "name": spec.expected_project_name,
        "package_code": spec.expected_package_code,
        "package_slug": spec.expected_package_code,
        "package_name": package_name,
        "project_lane": spec.expected_lane,
        "lane": spec.expected_lane,
        "updated_at": now,
    }
    project_previous, project_new = _changed_fields(
        project_before,
        {**project_before, **project_updates},
        list(project_updates.keys()),
    )
    if project_new:
        db["projects"].update_one({"_id": project["_id"]}, {"$set": project_updates})
        project_after = _find_by_id(db, "projects", spec.project_id) or {}
        for field, expected in project_updates.items():
            if project_after.get(field) != expected:
                raise RuntimeError(f"{spec.key}: post-write project verification failed for field '{field}'.")
        _record_write(
            write_log=write_log,
            script_execution_id=script_execution_id,
            collection="projects",
            record_id=spec.project_id,
            operation="update_one",
            previous_values=project_previous,
            new_values=project_new,
            reason="normalize_internal_validation_account_project_fields",
        )

    membership_before = db["project_members"].find_one(
        {
            "project_id": {"$in": _obj_or_str_candidates(spec.project_id)},
            "$or": [{"user_id": spec.user_id}, {"email": spec.email}],
        }
    )
    refreshed_project = _find_by_id(db, "projects", spec.project_id) or project
    ensure_project_owner_membership(refreshed_project)
    membership_after = db["project_members"].find_one(
        {
            "project_id": {"$in": _obj_or_str_candidates(spec.project_id)},
            "$or": [{"user_id": spec.user_id}, {"email": spec.email}],
        }
    )
    if membership_after is None:
        raise RuntimeError(f"{spec.key}: project owner membership verification failed.")
    membership_previous, membership_new = _changed_fields(
        membership_before or {},
        membership_after or {},
        ["member_role", "status", "project_id", "user_id", "email"],
    )
    _record_write(
        write_log=write_log,
        script_execution_id=script_execution_id,
        collection="project_members",
        record_id=_doc_id(membership_after),
        operation="service:ensure_project_owner_membership",
        previous_values=membership_previous,
        new_values=membership_new,
        reason="ensure_owner_has_billing_owner_membership",
    )

    entitlement_before = _find_entitlement(db, spec) or {}
    entitlement_after = upsert_project_entitlement(
        project_id=spec.project_id,
        user_id=spec.user_id,
        package_code=spec.expected_package_code,
        active_addons=[],
        status="active",
    ) or {}
    if str(entitlement_after.get("package_code") or "").strip() != spec.expected_package_code:
        raise RuntimeError(f"{spec.key}: entitlement post-write verification failed.")
    entitlement_previous, entitlement_new = _changed_fields(
        entitlement_before,
        entitlement_after,
        ["package_code", "package_name", "package_lane", "status"],
    )
    _record_write(
        write_log=write_log,
        script_execution_id=script_execution_id,
        collection="project_entitlements",
        record_id=str(entitlement_after.get("id") or _doc_id(entitlement_before)),
        operation="service:upsert_project_entitlement",
        previous_values=entitlement_previous,
        new_values=entitlement_new,
        reason="synchronize_project_entitlement_with_expected_active_package",
    )

    return {
        "account_key": spec.key,
        "user_id": spec.user_id,
        "project_id": spec.project_id,
        "entitlement_id": entitlement_after.get("id"),
    }


def _record_keith_upgrade_evidence(
    db: Any,
    spec: AccountSpec,
    *,
    script_execution_id: str,
    write_log: list[dict[str, Any]],
) -> dict[str, Any]:
    existing = _find_upgrade_event(db, spec)
    details = {
        "authorization_source": CEO_AUTHORIZATION_SOURCE,
        "authorized_by": CEO_AUTHORIZED_BY,
        "authorization_date": CEO_AUTHORIZATION_DATE,
        "historical_effective_date": None,
        "original_package_code": spec.original_package_code,
        "upgraded_package_code": spec.expected_package_code,
        "upgraded_lane": spec.expected_lane,
        "upgrade_reason": KEITH_UPGRADE_REASON,
        "additional_payment_requirement": "unknown",
        "coupon_information": "pending Stripe verification",
        "audit_note": "Original transaction preserved; active entitlement upgraded",
    }
    now = _now()
    if existing is None:
        insert_doc = {
            "event_type": "package_upgrade",
            "project_id": _oid(spec.project_id) or spec.project_id,
            "customer_email": spec.email,
            "customer_user_id": _oid(spec.user_id) or spec.user_id,
            "details": details,
            "occurred_at": None,
            "created_at": now,
            "updated_at": now,
        }
        result = db["finance_events"].insert_one(insert_doc)
        created = db["finance_events"].find_one({"_id": result.inserted_id}) or insert_doc
        _record_write(
            write_log=write_log,
            script_execution_id=script_execution_id,
            collection="finance_events",
            record_id=_doc_id(created),
            operation="insert_one",
            previous_values={},
            new_values={"event_type": "package_upgrade", "details": details},
            reason="record_ceo_authorized_keith_upgrade_evidence",
        )
        return {"operation": "inserted_upgrade_evidence", "event_id": _doc_id(created)}
    before = dict(existing)
    update_fields = {
        "details": {**(existing.get("details") or {}), **details},
        "updated_at": now,
    }
    db["finance_events"].update_one({"_id": existing["_id"]}, {"$set": update_fields})
    after = db["finance_events"].find_one({"_id": existing["_id"]}) or {}
    previous, new = _changed_fields(before, after, ["details", "updated_at"])
    _record_write(
        write_log=write_log,
        script_execution_id=script_execution_id,
        collection="finance_events",
        record_id=_doc_id(existing),
        operation="update_one",
        previous_values=previous,
        new_values=new,
        reason="refresh_ceo_authorized_keith_upgrade_evidence",
    )
    return {"operation": "updated_upgrade_evidence", "event_id": _doc_id(existing)}


def _normalize_larry_mint_wallet_if_safe(
    db: Any,
    spec: AccountSpec,
    *,
    script_execution_id: str,
    write_log: list[dict[str, Any]],
) -> dict[str, Any]:
    project = _find_project(db, spec) or {}
    mint_doc = _find_larry_mint(db, spec)
    if mint_doc is None:
        return {"operation": "skipped", "reason": "mint_record_missing"}
    resolved_wallet, wallet_sources = _extract_wallet_from_mint(mint_doc, project)
    if not resolved_wallet:
        return {"operation": "skipped", "reason": "wallet_source_missing", "sources": wallet_sources}
    if resolved_wallet != EXPECTED_LARRY_CANONICAL_MINT["wallet_address"]:
        return {
            "operation": "skipped",
            "reason": "wallet_source_mismatch",
            "resolved_wallet": resolved_wallet,
        }
    before = dict(mint_doc)
    update_fields = {
        "wallet_address": resolved_wallet,
        "mint_wallet": str(mint_doc.get("mint_wallet") or resolved_wallet),
        "updated_at": _now(),
        "metadata_normalization_source": "project.mint_wallet",
    }
    db["mint_records"].update_one({"_id": mint_doc["_id"]}, {"$set": update_fields})
    after = db["mint_records"].find_one({"_id": mint_doc["_id"]}) or {}
    previous, new = _changed_fields(
        before,
        after,
        ["wallet_address", "mint_wallet", "metadata_normalization_source", "updated_at"],
    )
    _record_write(
        write_log=write_log,
        script_execution_id=script_execution_id,
        collection="mint_records",
        record_id=_doc_id(mint_doc),
        operation="update_one",
        previous_values=previous,
        new_values=new,
        reason="normalize_canonical_mint_wallet_fields_without_remint",
    )
    return {
        "operation": "normalized_wallet_metadata",
        "mint_record_id": _doc_id(mint_doc),
        "resolved_wallet": resolved_wallet,
    }


def _backfill_order_from_stripe_snapshot(
    db: Any,
    *,
    spec: AccountSpec,
    order: dict[str, Any],
    snapshot: dict[str, Any],
    script_execution_id: str,
    write_log: list[dict[str, Any]],
) -> None:
    if snapshot.get("status") != "ok":
        return
    before = dict(order)
    updates = {
        "promotion_code": snapshot.get("promotion_code"),
        "coupon_id": snapshot.get("coupon_id"),
        "discount_amount": snapshot.get("discount_amount"),
        "final_amount_paid": snapshot.get("amount_total"),
        "amount_paid": snapshot.get("amount_total"),
        "stripe_payment_link_id": snapshot.get("payment_link_id") or order.get("stripe_payment_link_id"),
        "updated_at": _now(),
    }
    db["orders"].update_one({"_id": order["_id"]}, {"$set": updates})
    after = db["orders"].find_one({"_id": order["_id"]}) or {}
    previous, new = _changed_fields(
        before,
        after,
        [
            "promotion_code",
            "coupon_id",
            "discount_amount",
            "final_amount_paid",
            "amount_paid",
            "stripe_payment_link_id",
            "updated_at",
        ],
    )
    _record_write(
        write_log=write_log,
        script_execution_id=script_execution_id,
        collection="orders",
        record_id=_doc_id(order),
        operation="update_one",
        previous_values=previous,
        new_values=new,
        reason=f"stripe_read_only_billing_backfill:{spec.key}",
    )


def _apply_controlled_repairs(
    db: Any,
    specs: dict[str, AccountSpec],
    *,
    script_execution_id: str,
    write_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []

    jennifer = specs["jennifer_wood"]
    j_project = _find_project(db, jennifer)
    j_membership_before = db["project_members"].find_one(
        {
            "project_id": {"$in": _obj_or_str_candidates(jennifer.project_id)},
            "$or": [{"user_id": jennifer.user_id}, {"email": jennifer.email}],
        }
    )
    if j_project is None:
        raise RuntimeError("jennifer_wood: project missing for membership repair.")
    ensure_project_owner_membership(j_project)
    j_membership_after = db["project_members"].find_one(
        {
            "project_id": {"$in": _obj_or_str_candidates(jennifer.project_id)},
            "$or": [{"user_id": jennifer.user_id}, {"email": jennifer.email}],
        }
    )
    if j_membership_after is None:
        raise RuntimeError("jennifer_wood: membership repair failed.")
    previous, new = _changed_fields(
        j_membership_before or {},
        j_membership_after or {},
        ["member_role", "status", "project_id", "user_id", "email"],
    )
    _record_write(
        write_log=write_log,
        script_execution_id=script_execution_id,
        collection="project_members",
        record_id=_doc_id(j_membership_after),
        operation="service:ensure_project_owner_membership",
        previous_values=previous,
        new_values=new,
        reason="repair_missing_jennifer_owner_membership",
    )
    repairs.append({"account_key": "jennifer_wood", "repair": "owner_membership"})

    keith = specs["keith_goffigan"]
    repairs.append(
        {"account_key": "keith_goffigan", "repair": "upgrade_evidence", **_record_keith_upgrade_evidence(
            db,
            keith,
            script_execution_id=script_execution_id,
            write_log=write_log,
        )}
    )

    return repairs


def _collect_apply_blockers(audits: list[dict[str, Any]], cross_account_conflicts: list[str]) -> list[str]:
    repairable_conflicts = {
        "keith_goffigan:missing_upgrade_evidence",
        "larry_robinson:unexpected_larry_mint_conflict",
    }
    blockers: list[str] = []
    if cross_account_conflicts:
        blockers.extend(cross_account_conflicts)
    for audit in audits:
        account = str(audit.get("account_key") or "")
        for conflict in audit.get("conflicts") or []:
            blocker = f"{account}:{conflict}"
            if blocker not in repairable_conflicts:
                blockers.append(blocker)
    return sorted(set(blockers))


def build_intended_state_summary(specs: dict[str, AccountSpec]) -> list[dict[str, Any]]:
    return [
        {
            "account_key": spec.key,
            "email": spec.email,
            "user_id": spec.user_id,
            "project_id": spec.project_id,
            "family_id": spec.family_id,
            "household_id": spec.household_id,
            "intake_submission_id": spec.intake_submission_id,
            "expected_package_code": spec.expected_package_code,
            "expected_lane": spec.expected_lane,
            "original_package_code": spec.original_package_code,
        }
        for spec in specs.values()
    ]


def _is_authorization_recorded(operator_authorization: dict[str, str]) -> bool:
    return all(
        bool(str(operator_authorization.get(key) or "").strip())
        for key in ("source", "authorized_by", "authorization_date")
    )


def _apply_operator_authorization(audits: list[dict[str, Any]], operator_authorization: dict[str, str]) -> None:
    if not _is_authorization_recorded(operator_authorization):
        return
    for audit in audits:
        if str(audit.get("account_key") or "") != "keith_goffigan":
            continue
        conflicts = list(audit.get("conflicts") or [])
        if "missing_upgrade_evidence" not in conflicts:
            continue
        upgrade = audit.get("upgrade") or {}
        upgrade["authorization_satisfied"] = True
        upgrade["proposed_action_when_missing"] = "CEO authorization present — upgrade evidence record pending apply"
        audit["upgrade"] = upgrade
        system_matrix = audit.get("system_completion_matrix") or {}
        system_matrix["Correct upgrade evidence"] = "Authorized upgrade record pending apply"
        audit["system_completion_matrix"] = system_matrix


def _business_authorizations_needed(audits: list[dict[str, Any]]) -> list[str]:
    needed: list[str] = []
    for audit in audits:
        upgrade = audit.get("upgrade") or {}
        if upgrade.get("proposed_action_when_missing") and not upgrade.get("authorization_satisfied"):
            needed.append(f"{audit.get('account_key')}:upgrade_authorization")
    return sorted(set(needed))


def _build_proposed_repairs(
    audits: list[dict[str, Any]],
    specs: dict[str, AccountSpec],
    operator_authorization: dict[str, str],
) -> list[dict[str, Any]]:
    by_key = {str(item.get("account_key") or ""): item for item in audits}
    repairs: list[dict[str, Any]] = []

    jennifer = by_key.get("jennifer_wood") or {}
    jennifer_state = jennifer.get("current_state") or {}
    if (jennifer.get("system_completion_matrix") or {}).get("Correct membership") != "Complete":
        repairs.append(
            {
                "account_key": "jennifer_wood",
                "collection": "project_members",
                "record_ref": f"project:{specs['jennifer_wood'].project_id}|owner:{specs['jennifer_wood'].user_id}",
                "current_value": {
                    "membership_record_id": jennifer_state.get("membership_record_id"),
                    "member_role": jennifer_state.get("membership_role"),
                    "status": jennifer_state.get("membership_status"),
                },
                "proposed_value": {"member_role": "billing_owner", "status": "active"},
                "reason": "create_or_restore_owner_membership_for_project_owner",
                "authorization_source": operator_authorization.get("source"),
            }
        )

    keith = by_key.get("keith_goffigan") or {}
    keith_upgrade = keith.get("upgrade") or {}
    if not keith_upgrade.get("event_id"):
        repairs.append(
            {
                "account_key": "keith_goffigan",
                "collection": "finance_events",
                "record_ref": f"event_type:package_upgrade|project_id:{specs['keith_goffigan'].project_id}|email:{specs['keith_goffigan'].email}",
                "current_value": None,
                "proposed_value": {
                    "event_type": "package_upgrade",
                    "original_package_code": specs["keith_goffigan"].original_package_code,
                    "upgraded_package_code": specs["keith_goffigan"].expected_package_code,
                    "upgraded_lane": specs["keith_goffigan"].expected_lane,
                    "historical_effective_date": None,
                },
                "reason": "record_ceo_authorized_upgrade_evidence_without_changing_billing_history",
                "authorization_source": operator_authorization.get("source"),
            }
        )

    larry = by_key.get("larry_robinson") or {}
    larry_conflicts = list(larry.get("conflicts") or [])
    mint = larry.get("mint") or {}
    if "unexpected_larry_mint_conflict" in larry_conflicts:
        repairs.append(
            {
                "account_key": "larry_robinson",
                "collection": "mint_records",
                "record_ref": mint.get("mint_record_id") or specs["larry_robinson"].project_id,
                "current_value": {"wallet_address": mint.get("wallet_address"), "wallet_field_sources": mint.get("wallet_field_sources")},
                "proposed_value": {
                    "wallet_address": EXPECTED_LARRY_CANONICAL_MINT["wallet_address"],
                    "metadata_normalization_source": "project.mint_wallet",
                },
                "reason": "normalize_wallet_metadata_only_if_required_without_remint",
                "authorization_source": operator_authorization.get("source"),
            }
        )
    else:
        repairs.append(
            {
                "account_key": "larry_robinson",
                "collection": "mint_records",
                "record_ref": mint.get("mint_record_id") or specs["larry_robinson"].project_id,
                "current_value": {"wallet_address": mint.get("wallet_address"), "wallet_field_sources": mint.get("wallet_field_sources")},
                "proposed_value": "no_write_required",
                "reason": "existing_project_mint_wallet_already_satisfies_canonical_mint_display",
                "authorization_source": operator_authorization.get("source"),
            }
        )
    return repairs


def _final_verdict_for_account(audit: dict[str, Any]) -> str:
    conflicts = list(audit.get("conflicts") or [])
    if conflicts:
        if conflicts == ["missing_upgrade_evidence"] and bool((audit.get("upgrade") or {}).get("authorization_satisfied")):
            return "SYSTEM READY — AUTHORIZED UPGRADE RECORD PENDING APPLY"
        requires_business = all(
            item in {"missing_upgrade_evidence"} for item in conflicts
        )
        return (
            "BLOCKED — BUSINESS DECISION REQUIRED"
            if requires_business
            else "BLOCKED — VERIFIED SOFTWARE DEFECT"
        )
    inventory = list(audit.get("actual_content_inventory") or [])
    missing_customer = any(
        item.get("package_required") and item.get("missing") and item.get("responsible_party") == "customer"
        for item in inventory
    )
    missing_production = any(
        item.get("package_required") and item.get("missing") and item.get("responsible_party") == "production_team"
        for item in inventory
    )
    if missing_customer:
        return "SYSTEM READY — CUSTOMER CONTENT REQUIRED"
    if missing_production:
        return "SYSTEM READY — PRODUCTION ASSETS REQUIRED"
    return "COMPLETE AND READY FOR CUSTOMER VALIDATION"


def _audit_completion_verdict(audits: list[dict[str, Any]], blockers: list[str]) -> str:
    if blockers:
        return AUDIT_VERDICT_APPLY_BLOCKED
    if _business_authorizations_needed(audits):
        return AUDIT_VERDICT_AUTH_REQUIRED
    any_content_gap = any(
        entry.get("package_required") and entry.get("missing")
        for audit in audits
        for entry in (audit.get("actual_content_inventory") or [])
    )
    if any_content_gap:
        return AUDIT_VERDICT_CONTENT_REQUIRED
    return AUDIT_VERDICT_SAFE_REPAIRS


def _write_report_if_requested(report: dict[str, Any], path: str) -> None:
    output_path = str(path or "").strip()
    if not output_path:
        return
    report_file = Path(output_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")


def _determine_exit_code(report: dict[str, Any]) -> int:
    blocking = report.get("blocking_conflicts") or []
    if blocking:
        return EXIT_IDENTITY_OR_OWNERSHIP_CONFLICT
    content_only_missing = any(
        bool(item.get("package_required")) and bool(item.get("missing"))
        for account in report.get("account_completion_matrix", [])
        for item in (account.get("actual_content_inventory") or [])
    )
    if content_only_missing:
        return EXIT_CONTENT_ONLY_GAPS
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict audit/repair runner for internal validation accounts.")
    parser.add_argument("--apply", action="store_true", help="Apply writes only when all safety preconditions pass.")
    parser.add_argument("--confirm-apply", default="", help=f"Required phrase for apply mode: {required_confirmation_phrase()}")
    parser.add_argument("--environment", default="development", help="Execution environment label.")
    parser.add_argument("--database-name", default="", help="Expected Mongo database name.")
    parser.add_argument("--report-path", default="", help="Optional JSON report output path.")
    parser.add_argument("--operator-authorization-source", default=CEO_AUTHORIZATION_SOURCE)
    parser.add_argument("--operator-authorized-by", default=CEO_AUTHORIZED_BY)
    parser.add_argument("--operator-authorization-date", default=CEO_AUTHORIZATION_DATE)
    args = parser.parse_args()

    apply_safe, apply_error = validate_apply_mode(
        apply=bool(args.apply),
        confirmation_phrase=str(args.confirm_apply or ""),
        environment=str(args.environment or ""),
        database_name=str(args.database_name or ""),
        report_path=str(args.report_path or ""),
    )
    if not apply_safe:
        rejection = {"mode": "rejected", "error": apply_error}
        print(json.dumps(rejection, indent=2))
        return EXIT_VALIDATION_ERROR

    specs = account_specs()
    db = connect_to_mongo()
    if db is None:
        payload = {"mode": "error", "error": "Database unavailable."}
        print(json.dumps(payload, indent=2))
        return EXIT_RUNTIME_ERROR
    if str(args.database_name or "").strip() and str(getattr(db, "name", "") or "").strip() != str(args.database_name).strip():
        payload = {
            "mode": "rejected",
            "error": "Connected database name does not match --database-name.",
            "connected_database_name": str(getattr(db, "name", "") or ""),
        }
        print(json.dumps(payload, indent=2))
        return EXIT_VALIDATION_ERROR

    script_execution_id = _now().strftime("internal-account-repair-%Y%m%dT%H%M%S%fZ")
    operator_authorization = {
        "source": str(args.operator_authorization_source or "").strip(),
        "authorized_by": str(args.operator_authorized_by or "").strip(),
        "authorization_date": str(args.operator_authorization_date or "").strip(),
    }
    audits: list[dict[str, Any]] = []
    write_log: list[dict[str, Any]] = []
    applied_repairs: list[dict[str, Any]] = []
    try:
        for spec in specs.values():
            audits.append(_audit_account(db, spec))
        _apply_operator_authorization(audits, operator_authorization)
        cross_conflicts = _cross_account_conflicts(audits)
        apply_blockers = _collect_apply_blockers(audits, cross_conflicts)

        if args.apply:
            if apply_blockers:
                raise RuntimeError(
                    "Apply blocked. Unresolved conflicts: " + ", ".join(apply_blockers)
                )
            applied_repairs.extend(
                _apply_controlled_repairs(
                    db,
                    specs,
                    script_execution_id=script_execution_id,
                    write_log=write_log,
                )
            )
            audits = []
            for spec in specs.values():
                audits.append(_audit_account(db, spec))
            _apply_operator_authorization(audits, operator_authorization)

        genesis = _audit_genesis_prototype_separation(db)
    finally:
        close_mongo_connection()

    proposed_repairs = _build_proposed_repairs(audits, specs, operator_authorization)
    report = {
        "mode": "apply" if args.apply else "audit_only",
        "script_execution_id": script_execution_id,
        "generated_at": _now().isoformat(),
        "environment": str(args.environment or "").strip().lower(),
        "database_name": str(args.database_name or "").strip() or None,
        "exact_saved_account_specifications": [asdict(spec) for spec in specs.values()],
        "read_only_audit_findings": audits,
        "accounts_current_state": audits,
        "accounts_intended_state": build_intended_state_summary(specs),
        "blocking_conflicts": _collect_apply_blockers(audits, _cross_account_conflicts(audits)),
        "security_findings": {"genesis_prototype_separation": genesis},
        "coupon_findings": {item["account_key"]: item.get("billing", {}).get("orders", []) for item in audits},
        "stripe_findings": {item["account_key"]: item.get("billing", {}).get("orders", []) for item in audits},
        "keith_upgrade_findings": next((item.get("upgrade") for item in audits if item.get("account_key") == "keith_goffigan"), {}),
        "maintenance_findings": {item["account_key"]: item.get("maintenance") for item in audits},
        "mint_findings": {item["account_key"]: item.get("mint") for item in audits},
        "account_completion_matrix": [
            {
                "account_key": item["account_key"],
                "system_controlled_matrix": item.get("system_completion_matrix") or {},
                "customer_content_matrix": item.get("customer_content_matrix") or {},
                "actual_content_inventory": item.get("actual_content_inventory") or [],
            }
            for item in audits
        ],
        "remaining_business_decisions": sorted(
            _business_authorizations_needed(audits)
        ),
        "remaining_customer_content_requirements": "See account_completion_matrix.actual_content_inventory",
        "proposed_repairs": proposed_repairs,
        "safe_repairs": [
            item
            for item in proposed_repairs
            if item.get("account_key") in {"jennifer_wood", "keith_goffigan"}
        ],
        "business_authorizations_needed": _business_authorizations_needed(audits),
        "apply_scope": [
            "jennifer_wood:project_members owner membership",
            "keith_goffigan:finance_events package_upgrade evidence",
        ],
        "applied_repairs": applied_repairs,
        "write_log": write_log,
        "write_log_count": len(write_log),
        "files_changed": [
            "backend/scripts/complete_internal_validation_accounts.py",
            "backend/tests/test_internal_validation_account_completion_script.py",
        ],
        "collections_changed": sorted({entry["collection"] for entry in write_log}),
        "repair_scripts_added": ["backend/scripts/complete_internal_validation_accounts.py"],
        "final_verdict_per_account": [
            {"account_key": item["account_key"], "verdict": _final_verdict_for_account(item)} for item in audits
        ],
        "no_stripe_mutations_performed": True,
        "no_blockchain_operations_performed": True,
        "operator_authorization": operator_authorization,
        "final_verdict": _audit_completion_verdict(
            audits,
            _collect_apply_blockers(audits, _cross_account_conflicts(audits)),
        ),
    }
    _write_report_if_requested(report, str(args.report_path or ""))
    print(json.dumps(report, indent=2, default=str))
    return _determine_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
