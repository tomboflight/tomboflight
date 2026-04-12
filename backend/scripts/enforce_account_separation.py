#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.package_catalog import get_package, normalize_package_code
from app.core.package_type_catalog import normalize_package_type
from app.database import close_mongo_connection, connect_to_mongo
from app.services.entitlement_service import resolve_project_entitlements
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
        "department_role": "finance",
        "access_tier": "finance_admin",
    },
    "k.goffigan@tomboflight.com": {
        "full_name": "Keith Goffigan",
        "business_title": "COO",
        "department_role": "operations",
        "access_tier": "operations_admin",
    },
    "l.robinson@tomboflight.com": {
        "full_name": "Larry Robinson",
        "business_title": "CEO / Super Admin",
        "department_role": "executive_technology",
        "access_tier": "super_admin",
    },
    "marquis.l.floyd@tomboflight.com": {
        "full_name": "Marquis Floyd",
        "business_title": "CMO",
        "department_role": "marketing",
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
        maintenance_plan="monthly",
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
                maintenance_plan="monthly",
                status="active",
            )
            _record_action(
                actions,
                "refreshed_personal_entitlement",
                email=email,
                project_id=project_id,
                entitlement_id=(entitlement or {}).get("id"),
            )


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
        _deactivate_admin_entitlements(
            db,
            apply=args.apply,
            actions=actions,
            admin_users=admin_users,
        )
    finally:
        close_mongo_connection()

    print(json.dumps({"mode": "apply" if args.apply else "dry_run", "actions": actions}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
