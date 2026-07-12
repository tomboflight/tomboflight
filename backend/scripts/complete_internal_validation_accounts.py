#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

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
EXPECTED_LARRY_CANONICAL_MINT = {
    "token_id": "1",
    "chain": "base-mainnet",
    "contract_address": "0x39967cEb7580aB9110b349Ca3a7fe0179b950Ba5",
    "tx_hash": "0xae659f5c6e2280932fadb4bd6c7b7cd0d37e9d75bde54589be736f32f810de1a",
    "wallet_address": "0xAdD4567249354c3B54f77313bf874d50179DB479",
    "mint_record_id": "69cae30f786977dfd046eaef",
    "version_number": 2,
}


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


def _obj_or_str_candidates(raw_id: str) -> list[Any]:
    oid = _oid(raw_id)
    return [oid, raw_id] if oid is not None else [raw_id]


def _safe_count(db: Any, collection: str, query: dict[str, Any]) -> int:
    try:
        return int(db[collection].count_documents(query))
    except Exception:
        return 0


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


def _package_name(package_code: str) -> str:
    package = get_package(package_code) or {}
    return str(package.get("display_name") or package_code.replace("_", " ").title())


def _maintenance_classification(entitlement: dict[str, Any], orders: list[dict[str, Any]]) -> str:
    status = str(entitlement.get("maintenance_status") or "").strip().lower()
    plan = str(entitlement.get("maintenance_plan") or "").strip().lower()
    has_subscription = bool(entitlement.get("maintenance_stripe_subscription_id"))
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


def _content_completion_matrix() -> dict[str, str]:
    return {
        "Portrait image": "Requires customer",
        "Biography or legacy story": "Requires customer",
        "Supporting photographs": "Requires customer",
        "Household member information": "Requires customer",
        "Relationship information": "Requires customer",
        "Voice recordings": "Requires customer",
        "Videos": "Requires customer",
        "Documents": "Requires customer",
        "Scheduled messages": "Requires customer",
        "Time-lock dates": "Requires customer",
        "Customer review": "Requires customer",
        "Customer approval": "Requires customer",
        "Final production assets": "Requires production team",
    }


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
    if spec.key == "larry_robinson":
        mint_doc = _find_larry_mint(db, spec)
        mint = {
            "mint_record_id": _doc_id(mint_doc),
            "token_id": str((mint_doc or {}).get("token_id") or (mint_doc or {}).get("public_token_id") or ""),
            "chain": str((mint_doc or {}).get("chain") or ""),
            "contract_address": str((mint_doc or {}).get("contract_address") or ""),
            "tx_hash": str((mint_doc or {}).get("tx_hash") or ""),
            "wallet_address": str((mint_doc or {}).get("wallet_address") or ""),
            "version_number": (mint_doc or {}).get("version_number"),
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
        },
        "billing": {
            "orders": orders,
            "coupon_evidence_present": any(bool(item.get("promotion_code") or item.get("coupon_id")) for item in orders),
        },
        "upgrade": {
            "event_id": _doc_id(upgrade_event) or None,
            "details": (upgrade_event or {}).get("details"),
            "proposed_action_when_missing": (
                "Missing verified source data — no write performed"
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
        "customer_content_matrix": _content_completion_matrix(),
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


def _collect_apply_blockers(audits: list[dict[str, Any]], cross_account_conflicts: list[str]) -> list[str]:
    blockers: list[str] = []
    if cross_account_conflicts:
        blockers.extend(cross_account_conflicts)
    for audit in audits:
        account = str(audit.get("account_key") or "")
        for conflict in audit.get("conflicts") or []:
            blockers.append(f"{account}:{conflict}")
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


def _final_verdict_for_account(audit: dict[str, Any]) -> str:
    conflicts = list(audit.get("conflicts") or [])
    if conflicts:
        return "FAIL — A core package, billing, security, or delivery function is not working"
    if any(value in {"Requires customer", "Requires production team"} for value in (audit.get("customer_content_matrix") or {}).values()):
        return "CONDITIONAL PASS — Platform works, but named customer-supplied content remains"
    return "PASS — Complete and production-ready"


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
        value in {"Requires customer", "Requires production team"}
        for account in report.get("account_completion_matrix", [])
        for value in (account.get("customer_content_matrix") or {}).values()
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
    audits: list[dict[str, Any]] = []
    write_log: list[dict[str, Any]] = []
    applied_repairs: list[dict[str, Any]] = []
    try:
        for spec in specs.values():
            audits.append(_audit_account(db, spec))
        cross_conflicts = _cross_account_conflicts(audits)
        apply_blockers = _collect_apply_blockers(audits, cross_conflicts)

        if args.apply:
            if apply_blockers:
                raise RuntimeError(
                    "Apply blocked. Unresolved conflicts: " + ", ".join(apply_blockers)
                )
            for spec in specs.values():
                applied_repairs.append(
                    _apply_one_account(
                        db,
                        spec,
                        script_execution_id=script_execution_id,
                        write_log=write_log,
                    )
                )

        genesis = _audit_genesis_prototype_separation(db)
    finally:
        close_mongo_connection()

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
            }
            for item in audits
        ],
        "remaining_business_decisions": sorted(
            {
                "Missing verified source data — no write performed"
                for item in audits
                if (item.get("upgrade") or {}).get("proposed_action_when_missing")
            }
        ),
        "remaining_customer_content_requirements": "See account_completion_matrix.customer_content_matrix",
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
        "final_verdict": (
            "SAFE FOR READ-ONLY PRODUCTION AUDIT"
            if not _collect_apply_blockers(audits, _cross_account_conflicts(audits))
            else "NOT SAFE FOR PRODUCTION AUDIT"
        ),
    }
    _write_report_if_requested(report, str(args.report_path or ""))
    print(json.dumps(report, indent=2, default=str))
    return _determine_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
