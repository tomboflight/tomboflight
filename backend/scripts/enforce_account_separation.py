#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.package_catalog import (
    get_package,
    get_package_control_profile,
    normalize_package_code,
)
from app.core.package_type_catalog import normalize_package_type
from app.database import close_mongo_connection, connect_to_mongo
from app.services.admin_access_bootstrap_service import bootstrap_admin_access_controls
from app.services.entitlement_service import resolve_project_entitlements
from app.services.mint_record_service import (
    approve_admin_mint_record,
    approve_customer_mint_record,
    create_mint_record,
    mark_mint_minted,
    resolve_canonical_mint_status,
)
from app.services.project_entitlement_service import upsert_project_entitlement
from app.services.project_membership_service import ensure_project_owner_membership

GENESIS_EMAIL = "larry.frontend.test2@tomboflight.com"
GENESIS_PROJECT_NAME = "Genesis Prototype"
GENESIS_PACKAGE_CODE = "household_foundation"
GENESIS_FAMILY_NAME = "Moreland Family"

PERSONAL_ACCOUNTS: dict[str, dict[str, str]] = {
    "queenjwood@gmail.com": {"full_name": "Jennifer Wood", "account_type": "customer"},
    "chief757@outlook.com": {"full_name": "Keith Goffigan", "account_type": "customer"},
    "larrycr27@gmail.com": {"full_name": "Larry Robinson", "account_type": "customer"},
    GENESIS_EMAIL: {
        "full_name": GENESIS_PROJECT_NAME,
        "account_type": "prototype_customer",
        "prototype_key": "genesis_prototype",
    },
    "mlfloyd00@gmail.com": {"full_name": "Marquis Floyd", "account_type": "customer"},
}

ADMIN_ACCOUNTS: dict[str, dict[str, str]] = {
    "jenn.wood@tomboflight.com": {
        "full_name": "Jennifer Wood",
        "business_title": "CFO",
        "department_role": "finance_admin",
        "access_tier": "finance_admin",
    },
    "k.goffigan@tomboflight.com": {
        "full_name": "Keith Goffigan",
        "business_title": "COO",
        "department_role": "operations_admin",
        "access_tier": "operations_admin",
    },
    "l.robinson@tomboflight.com": {
        "full_name": "Larry Robinson",
        "business_title": "CEO",
        "department_role": "executive_tech_admin",
        "access_tier": "super_admin",
    },
    "marquis.l.floyd@tomboflight.com": {
        "full_name": "Marquis Floyd",
        "business_title": "CMO",
        "department_role": "marketing_admin",
        "access_tier": "marketing_admin",
    },
}

PERSONAL_UNSET_FIELDS = [
    "access_tier",
    "department_role",
    "business_title",
    "company_title",
    "job_title",
    "staff_title",
    "admin_title",
]

ADMIN_UNSET_FIELDS = [
    "prototype_key",
    "package_code",
    "package_name",
    "package_lane",
    "customer_package_code",
    "customer_package_name",
    "creator_credit",
]

TARGET_PERSONAL_ACCOUNT_EXPERIENCE: dict[str, dict[str, str]] = {
    "queenjwood@gmail.com": {
        "package_code": "digital_legacy_portrait",
        "project_name": "Jennifer Wood Digital Legacy Portrait",
        "wallet_address": "0x1111111111111111111111111111111111111111",
    },
    "larrycr27@gmail.com": {
        "package_code": "legacy_plus",
        "project_name": "Larry Robinson Legacy Plus",
        "wallet_address": "0x3333333333333333333333333333333333333333",
    },
    "mlfloyd00@gmail.com": {
        "package_code": "digital_legacy_portrait",
        "project_name": "Marquis Floyd Digital Legacy Portrait",
        "wallet_address": "0x2222222222222222222222222222222222222222",
    },
}


def _now() -> datetime:
    return datetime.now(UTC)


def _oid(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    text = str(value or "").strip()
    if ObjectId.is_valid(text):
        return ObjectId(text)
    return None


def _doc_id(document: dict[str, Any] | None) -> str:
    return str((document or {}).get("_id") or "")


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


def _record_action(actions: list[dict[str, Any]], action: str, **details: Any) -> None:
    actions.append({"action": action, **_serialize(details)})


def _maintenance_plan_for_package(package_code: str) -> str:
    profile = get_package_control_profile(package_code) or {}
    normalized = str(profile.get("maintenance_default") or "none").strip().lower()
    if normalized in {"monthly", "yearly", "none"}:
        return normalized
    return "none"


def _update_one(
    collection,
    query: dict[str, Any],
    *,
    set_fields: dict[str, Any] | None = None,
    unset_fields: list[str] | None = None,
    apply: bool,
    actions: list[dict[str, Any]],
    label: str,
) -> None:
    update: dict[str, Any] = {}
    if set_fields:
        update["$set"] = set_fields
    if unset_fields:
        update["$unset"] = {field: "" for field in unset_fields}
    if not update:
        return

    if not apply:
        _record_action(actions, "would_update", collection=collection.name, label=label, update=update)
        return

    result = collection.update_one(query, update)
    _record_action(
        actions,
        "updated",
        collection=collection.name,
        label=label,
        matched=result.matched_count,
        modified=result.modified_count,
    )


def _require_user(db, email: str) -> dict[str, Any]:
    user = db["users"].find_one({"email": email})
    if not user:
        raise RuntimeError(f"Required user not found: {email}")
    return user


def _normalize_personal_accounts(
    db,
    *,
    apply: bool,
    actions: list[dict[str, Any]],
    creator: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    users: dict[str, dict[str, Any]] = {}
    creator_credit = "Larry Robinson, creator and owner of Tomb of Light"

    for email, config in PERSONAL_ACCOUNTS.items():
        user = _require_user(db, email)
        set_fields: dict[str, Any] = {
            "email": email,
            "full_name": config["full_name"],
            "role": "user",
            "account_type": config["account_type"],
            "status": "active",
            "updated_at": _now(),
        }

        if email == GENESIS_EMAIL:
            set_fields.update(
                {
                    "prototype_key": "genesis_prototype",
                    "creator_credit": creator_credit,
                    "creator_user_id": _doc_id(creator),
                    "creator_email": creator.get("email"),
                    "creator_name": creator.get("full_name") or "Larry Robinson",
                }
            )
        if email in TARGET_PERSONAL_ACCOUNT_EXPERIENCE:
            package_code = normalize_package_code(
                TARGET_PERSONAL_ACCOUNT_EXPERIENCE[email].get("package_code")
            )
            package = get_package(package_code) or {}
            set_fields.update(
                {
                    "package_code": package_code,
                    "package_name": package.get("display_name") or "Digital Legacy Portrait",
                    "package_lane": normalize_package_type(package.get("package_lane"), default="portrait"),
                    "verification_status": "verified",
                    "identity_verification_status": "verified",
                    "account_verification_state": "complete",
                    "mint_readiness_status": "minted",
                }
            )

        _update_one(
            db["users"],
            {"_id": user["_id"]},
            set_fields=set_fields,
            unset_fields=PERSONAL_UNSET_FIELDS,
            apply=apply,
            actions=actions,
            label=email,
        )
        users[email] = db["users"].find_one({"_id": user["_id"]}) or user

    return users


def _normalize_admin_accounts(
    db,
    *,
    apply: bool,
    actions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    users: dict[str, dict[str, Any]] = {}

    for email, config in ADMIN_ACCOUNTS.items():
        user = _require_user(db, email)
        set_fields = {
            "email": email,
            "full_name": config["full_name"],
            "role": "admin",
            "account_type": "business_admin",
            "business_title": config["business_title"],
            "department_role": config["department_role"],
            "access_tier": config["access_tier"],
            "status": "active",
            "updated_at": _now(),
        }
        _update_one(
            db["users"],
            {"_id": user["_id"]},
            set_fields=set_fields,
            unset_fields=ADMIN_UNSET_FIELDS,
            apply=apply,
            actions=actions,
            label=email,
        )
        users[email] = db["users"].find_one({"_id": user["_id"]}) or user

    return users


def _find_genesis_project(db) -> dict[str, Any]:
    project = db["projects"].find_one({"project_name": GENESIS_PROJECT_NAME})
    if project is None:
        project = db["projects"].find_one({"name": GENESIS_PROJECT_NAME})
    if project is None:
        raise RuntimeError(f"Required project not found: {GENESIS_PROJECT_NAME}")
    return project


def _find_moreland_family(db) -> dict[str, Any]:
    family = db["families"].find_one({"family_name": GENESIS_FAMILY_NAME})
    if family is None:
        family = db["families"].find_one(
            {"description": {"$regex": "Genesis prototype|Moreland", "$options": "i"}}
        )
    if family is None:
        raise RuntimeError(f"Required family not found: {GENESIS_FAMILY_NAME}")
    return family


def _normalize_project_order_and_entitlement(
    db,
    *,
    apply: bool,
    actions: list[dict[str, Any]],
    genesis_user: dict[str, Any],
    creator: dict[str, Any],
) -> None:
    project = _find_genesis_project(db)
    family = _find_moreland_family(db)
    package_code = normalize_package_code(GENESIS_PACKAGE_CODE)
    package = get_package(package_code) or {}
    package_name = str(package.get("display_name") or "Household Foundation")
    package_lane = normalize_package_type(package.get("package_lane"), default="household")
    project_id = _doc_id(project)
    genesis_user_id = _doc_id(genesis_user)
    creator_credit = "Larry Robinson, creator and owner of Tomb of Light"
    now = _now()

    project_fields = {
        "name": GENESIS_PROJECT_NAME,
        "project_name": GENESIS_PROJECT_NAME,
        "project_lane": package_lane,
        "lane": package_lane,
        "owner_user_id": genesis_user_id,
        "owner_email": GENESIS_EMAIL,
        "owner_name": GENESIS_PROJECT_NAME,
        "package_code": package_code,
        "package_slug": package_code,
        "package_type": package_code,
        "package_name": package_name,
        "item_type": "package",
        "billing_plan": "one_time",
        "status": "delivered",
        "phase": "delivery_complete",
        "source": "genesis_prototype_homepage",
        "family_id": _doc_id(family),
        "prototype_key": "genesis_prototype",
        "customer_experience": "homepage_prototype",
        "creator_credit": creator_credit,
        "creator_user_id": _doc_id(creator),
        "creator_email": creator.get("email"),
        "creator_name": creator.get("full_name") or "Larry Robinson",
        "updated_at": now,
    }
    _update_one(
        db["projects"],
        {"_id": project["_id"]},
        set_fields=project_fields,
        apply=apply,
        actions=actions,
        label=GENESIS_PROJECT_NAME,
    )

    family_fields = {
        "project_id": project_id,
        "owner_user_id": genesis_user_id,
        "owner_email": GENESIS_EMAIL,
        "package_code": package_code,
        "package_name": package_name,
        "prototype_key": "genesis_prototype",
        "creator_credit": creator_credit,
        "creator_user_id": _doc_id(creator),
        "creator_email": creator.get("email"),
        "created_by": creator.get("full_name") or "Larry Robinson",
        "updated_at": now,
    }
    _update_one(
        db["families"],
        {"_id": family["_id"]},
        set_fields=family_fields,
        apply=apply,
        actions=actions,
        label=GENESIS_FAMILY_NAME,
    )

    order = db["orders"].find_one({"email": GENESIS_EMAIL}, sort=[("created_at", -1)])
    if order is not None:
        order_fields = {
            "user_id": genesis_user_id,
            "email": GENESIS_EMAIL,
            "project_id": project_id,
            "package_code": package_code,
            "package_slug": package_code,
            "package_type": package_code,
            "package_name": package_name,
            "item_type": "package",
            "billing_plan": "one_time",
            "status": "paid",
            "price_label": order.get("price_label") or "$799",
            "updated_at": now,
        }
        _update_one(
            db["orders"],
            {"_id": order["_id"]},
            set_fields=order_fields,
            apply=apply,
            actions=actions,
            label=f"{GENESIS_EMAIL} paid package order",
        )

    if not apply:
        resolved = resolve_project_entitlements(package_code, [])
        _record_action(
            actions,
            "would_upsert_entitlement",
            project_id=project_id,
            user_id=genesis_user_id,
            package_code=package_code,
            package_name=resolved.get("display_name"),
        )
        _record_action(
            actions,
            "would_ensure_project_owner_membership",
            project_id=project_id,
            user_id=genesis_user_id,
            email=GENESIS_EMAIL,
        )
        return

    refreshed_project = db["projects"].find_one({"_id": project["_id"]}) or project
    ensure_project_owner_membership(refreshed_project)
    entitlement = upsert_project_entitlement(
        project_id=project_id,
        user_id=genesis_user_id,
        package_code=package_code,
        active_addons=[],
        maintenance_plan=_maintenance_plan_for_package(package_code),
        status="active",
    )
    _record_action(actions, "upserted_entitlement", entitlement=entitlement)


def _refresh_personal_project_entitlements(
    db,
    *,
    apply: bool,
    actions: list[dict[str, Any]],
    users: dict[str, dict[str, Any]],
) -> None:
    for email, user in users.items():
        user_id = _doc_id(user)
        projects = db["projects"].find(
            {"$or": [{"owner_user_id": user_id}, {"owner_email": email}]}
        )
        for project in projects:
            package_code = normalize_package_code(
                project.get("package_code")
                or project.get("package_slug")
                or project.get("package_type")
            )
            if not package_code:
                continue
            project_id = _doc_id(project)
            if not apply:
                _record_action(
                    actions,
                    "would_refresh_personal_entitlement",
                    email=email,
                    project_id=project_id,
                    package_code=package_code,
                )
                continue
            entitlement = upsert_project_entitlement(
                project_id=project_id,
                user_id=user_id,
                package_code=package_code,
                active_addons=[],
                maintenance_plan=_maintenance_plan_for_package(package_code),
                status="active",
            )
            _record_action(
                actions,
                "refreshed_personal_entitlement",
                email=email,
                project_id=project_id,
                entitlement_id=(entitlement or {}).get("id"),
            )


def _project_ref_value(project_id: str) -> ObjectId | str:
    return _oid(project_id) or project_id


def _id_text(value: Any) -> str:
    return str(value or "").strip()


def _tx_hash(email: str, project_id: str) -> str:
    digest = hashlib.sha256(f"{email}:{project_id}:minted".encode("utf-8")).hexdigest()
    return f"0x{digest}"


def _token_id(email: str, project_id: str) -> str:
    digest = hashlib.sha256(f"{email}:{project_id}:token".encode("utf-8")).hexdigest()
    return str(int(digest[:16], 16))


def _ensure_target_personal_account_experience(
    db,
    *,
    apply: bool,
    actions: list[dict[str, Any]],
    users: dict[str, dict[str, Any]],
) -> None:
    now = _now()
    for email, config in TARGET_PERSONAL_ACCOUNT_EXPERIENCE.items():
        user = users.get(email)
        if not user:
            continue
        user_id = _doc_id(user)
        package_code = normalize_package_code(config.get("package_code"))
        package = get_package(package_code) or {}
        package_name = package.get("display_name") or "Digital Legacy Portrait"
        package_lane = normalize_package_type(package.get("package_lane"), default="portrait")
        project = db["projects"].find_one(
            {"$or": [{"owner_user_id": user_id}, {"owner_email": email}]},
            sort=[("updated_at", -1), ("created_at", -1)],
        )

        project_fields = {
            "name": config.get("project_name"),
            "project_name": config.get("project_name"),
            "owner_user_id": user_id,
            "owner_email": email,
            "package_code": package_code,
            "package_slug": package_code,
            "package_type": package_code,
            "package_name": package_name,
            "project_lane": package_lane,
            "lane": package_lane,
            "item_type": "package",
            "billing_plan": "one_time",
            "status": "delivered",
            "phase": "delivery_complete",
            "source": "fictional_personal_account_bootstrap",
            "updated_at": now,
        }
        if project is None:
            if not apply:
                _record_action(actions, "would_create_target_project", email=email, project=project_fields)
                continue
            project_insert = dict(project_fields)
            project_insert["created_at"] = now
            result = db["projects"].insert_one(project_insert)
            project = db["projects"].find_one({"_id": result.inserted_id}) or {
                "_id": result.inserted_id,
                **project_insert,
            }
            _record_action(actions, "created_target_project", email=email, project_id=_doc_id(project))
        else:
            _update_one(
                db["projects"],
                {"_id": project["_id"]},
                set_fields=project_fields,
                apply=apply,
                actions=actions,
                label=f"{email} project package normalization",
            )
            project = db["projects"].find_one({"_id": project["_id"]}) or project
        project_id = _doc_id(project)
        family_id = _id_text(project.get("family_id"))

        order = db["orders"].find_one({"email": email}, sort=[("created_at", -1)])
        order_fields = {
            "email": email,
            "user_id": _project_ref_value(user_id),
            "project_id": _project_ref_value(project_id),
            "package_code": package_code,
            "package_slug": package_code,
            "package_type": package_code,
            "package_name": package_name,
            "item_type": "package",
            "billing_plan": "one_time",
            "status": "paid",
            "price_label": "$399",
            "updated_at": now,
        }
        if order is None:
            if not apply:
                _record_action(actions, "would_create_target_order", email=email, order=order_fields)
            else:
                order_insert = dict(order_fields)
                order_insert["created_at"] = now
                db["orders"].insert_one(order_insert)
                _record_action(actions, "created_target_order", email=email, project_id=project_id)
        else:
            _update_one(
                db["orders"],
                {"_id": order["_id"]},
                set_fields=order_fields,
                apply=apply,
                actions=actions,
                label=f"{email} paid package order",
            )

        if not apply:
            _record_action(
                actions,
                "would_refresh_target_entitlement",
                email=email,
                project_id=project_id,
                package_code=package_code,
            )
        else:
            ensure_project_owner_membership(project)
            entitlement = upsert_project_entitlement(
                project_id=project_id,
                user_id=user_id,
                package_code=package_code,
                active_addons=[],
                maintenance_plan=_maintenance_plan_for_package(package_code),
                status="active",
            )
            _record_action(
                actions,
                "refreshed_target_entitlement",
                email=email,
                project_id=project_id,
                entitlement_id=(entitlement or {}).get("id"),
            )

        upload = db["uploaded_files"].find_one(
            {"project_id": {"$in": [_project_ref_value(project_id), project_id]}},
            sort=[("created_at", -1)],
        )
        if upload is None:
            upload_doc = {
                "project_id": _project_ref_value(project_id),
                "family_id": _project_ref_value(family_id) if family_id else None,
                "category": "verification_evidence",
                "status": "approved",
                "verification_status": "approved",
                "uploaded_by": email,
                "filename": f"{package_code}-evidence.txt",
                "original_filename": f"{package_code}-evidence.txt",
                "created_at": now,
                "updated_at": now,
            }
            if not apply:
                _record_action(actions, "would_create_target_upload", email=email, project_id=project_id)
            else:
                db["uploaded_files"].insert_one(upload_doc)
                _record_action(actions, "created_target_upload", email=email, project_id=project_id)

        record_query = {
            "project_id": _project_ref_value(project_id),
            "full_name": user.get("full_name") or config.get("project_name"),
            "verification_type": "identity_review",
        }
        verification_record = db["verification_records"].find_one(record_query)
        verification_fields = {
            "project_id": _project_ref_value(project_id),
            "family_id": _project_ref_value(family_id) if family_id else None,
            "full_name": user.get("full_name") or config.get("project_name"),
            "verification_type": "identity_review",
            "record_type": "identity_review",
            "verification_method": "admin_review",
            "verification_status": "verified",
            "status": "verified",
            "reviewed_by": "system.account-separation",
            "verified_by": "system.account-separation",
            "review_notes": "Fictional demo account verification completed.",
            "notes": "Fictional demo account verification completed.",
            "reviewed_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        if verification_record is None:
            verification_fields["created_at"] = now.isoformat()
            if not apply:
                _record_action(
                    actions,
                    "would_create_target_verification_record",
                    email=email,
                    project_id=project_id,
                )
            else:
                db["verification_records"].insert_one(verification_fields)
                _record_action(
                    actions,
                    "created_target_verification_record",
                    email=email,
                    project_id=project_id,
                )
        else:
            _update_one(
                db["verification_records"],
                {"_id": verification_record["_id"]},
                set_fields=verification_fields,
                apply=apply,
                actions=actions,
                label=f"{email} verification record",
            )

        canonical = resolve_canonical_mint_status(project_id, include_history=False)
        if canonical.get("current_status") == "minted":
            _record_action(actions, "target_project_already_minted", email=email, project_id=project_id)
            continue
        if not apply:
            _record_action(actions, "would_mark_target_project_minted", email=email, project_id=project_id)
            continue
        mint_record = create_mint_record(
            project_id,
            version_strategy="force_new_version",
            poster_style="abstract_cover",
            public_title_opt_in=False,
        )
        mint_record_id = str(mint_record.get("id"))
        approve_admin_mint_record(
            mint_record_id,
            approved_by_email="ops@tomboflight.com",
            notes="Fictional completion for personal demo account.",
        )
        approve_customer_mint_record(
            mint_record_id,
            approved_by_user_id=user_id,
            approved_by_email=email,
            notes="Customer approval for fictional demo profile.",
            wallet_address=config.get("wallet_address"),
            approved_poster_opt_in=False,
            public_title_opt_in=False,
            public_title=None,
            public_title_kind="none",
        )
        minted = mark_mint_minted(
            mint_record_id,
            token_id=_token_id(email, project_id),
            tx_hash=_tx_hash(email, project_id),
            minted_by="account_separation_script",
        )
        _record_action(
            actions,
            "marked_target_project_minted",
            email=email,
            project_id=project_id,
            mint_record_id=mint_record_id,
            token_id=minted.get("token_id"),
        )


def _target_account_standings(db, users: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    standings: list[dict[str, Any]] = []
    for email in TARGET_PERSONAL_ACCOUNT_EXPERIENCE:
        user = users.get(email)
        if not user:
            continue
        user_id = _doc_id(user)
        projects = list(
            db["projects"]
            .find({"$or": [{"owner_user_id": user_id}, {"owner_email": email}]})
            .sort("updated_at", -1)
        )
        project_ids = [_doc_id(project) for project in projects if _doc_id(project)]
        canonical_status = "none"
        latest_project_id = project_ids[0] if project_ids else ""
        if latest_project_id:
            canonical = resolve_canonical_mint_status(latest_project_id, include_history=False)
            canonical_status = str(canonical.get("current_status") or "none")
        paid_orders = db["orders"].count_documents({"email": email, "status": {"$in": ["paid", "succeeded", "completed"]}})
        active_entitlements = db["project_entitlements"].count_documents(
            {
                "user_id": {"$in": [_project_ref_value(user_id), user_id]},
                "status": "active",
            }
        )
        upload_count = db["uploaded_files"].count_documents(
            {"project_id": {"$in": [_project_ref_value(pid) for pid in project_ids] + project_ids}}
        )
        verification_count = db["verification_records"].count_documents(
            {
                "verification_status": "verified",
                "$or": [
                    {"project_id": {"$in": [_project_ref_value(pid) for pid in project_ids] + project_ids}},
                    {"full_name": user.get("full_name")},
                ],
            }
        )
        standings.append(
            {
                "email": email,
                "full_name": user.get("full_name"),
                "project_count": len(projects),
                "latest_project_id": latest_project_id or None,
                "paid_order_count": paid_orders,
                "active_entitlement_count": active_entitlements,
                "verified_record_count": verification_count,
                "uploaded_file_count": upload_count,
                "canonical_mint_status": canonical_status,
            }
        )
    return standings


def _deactivate_admin_entitlements(
    db,
    *,
    apply: bool,
    actions: list[dict[str, Any]],
    admin_users: dict[str, dict[str, Any]],
) -> None:
    admin_object_ids = [
        _oid(user.get("_id"))
        for user in admin_users.values()
        if _oid(user.get("_id")) is not None
    ]
    if not admin_object_ids:
        return

    query = {"user_id": {"$in": admin_object_ids}, "status": "active"}
    count = db["project_entitlements"].count_documents(query)
    if not count:
        _record_action(actions, "admin_entitlement_check", active_admin_entitlements=0)
        return

    update = {
        "$set": {
            "status": "inactive",
            "deactivated_reason": "business_admin_accounts_do_not_receive_customer_package_access",
            "updated_at": _now(),
        }
    }
    if not apply:
        _record_action(actions, "would_deactivate_admin_entitlements", count=count)
        return

    result = db["project_entitlements"].update_many(query, update)
    _record_action(
        actions,
        "deactivated_admin_entitlements",
        matched=result.matched_count,
        modified=result.modified_count,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce Tomb of Light personal/admin account separation."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Omit for a dry-run report.",
    )
    args = parser.parse_args()

    actions: list[dict[str, Any]] = []
    account_standings: list[dict[str, Any]] = []
    db = connect_to_mongo()
    try:
        creator = _require_user(db, "l.robinson@tomboflight.com")
        admin_users = _normalize_admin_accounts(db, apply=args.apply, actions=actions)
        personal_users = _normalize_personal_accounts(
            db,
            apply=args.apply,
            actions=actions,
            creator=creator,
        )
        _normalize_project_order_and_entitlement(
            db,
            apply=args.apply,
            actions=actions,
            genesis_user=personal_users[GENESIS_EMAIL],
            creator=creator,
        )
        _refresh_personal_project_entitlements(
            db,
            apply=args.apply,
            actions=actions,
            users=personal_users,
        )
        _ensure_target_personal_account_experience(
            db,
            apply=args.apply,
            actions=actions,
            users=personal_users,
        )
        _deactivate_admin_entitlements(
            db,
            apply=args.apply,
            actions=actions,
            admin_users=admin_users,
        )
        if args.apply:
            sync_stats = bootstrap_admin_access_controls()
            _record_action(actions, "synced_admin_access_controls", stats=sync_stats)
        else:
            _record_action(actions, "would_sync_admin_access_controls")
        account_standings = _target_account_standings(db, personal_users)
    finally:
        close_mongo_connection()

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry_run",
                "actions": actions,
                "account_standings": account_standings,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
