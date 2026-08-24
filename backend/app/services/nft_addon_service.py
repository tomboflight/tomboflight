from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, cast

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings
from app.core.package_catalog import (
    get_addon,
    get_package_control_profile,
    normalize_addon_code,
)
from app.database import get_database


INITIAL_MINT_ADDON_CODE = "nft_lineage_record"
ADDITIONAL_MINT_ADDON_CODE = "additional_nft_copy_mint"
METADATA_REVISION_ADDON_CODE = "nft_metadata_revision"
NFT_ADDON_CODES = frozenset(
    {
        INITIAL_MINT_ADDON_CODE,
        ADDITIONAL_MINT_ADDON_CODE,
        METADATA_REVISION_ADDON_CODE,
    }
)
MINT_ADDON_CODES = frozenset({INITIAL_MINT_ADDON_CODE, ADDITIONAL_MINT_ADDON_CODE})
AUTHORITATIVE_ORDER_SOURCES = frozenset(
    {"stripe_webhook", "stripe_verified"}
)
PAID_ORDER_STATUSES = frozenset({"paid", "complete", "completed", "succeeded"})
COMPLETE_PROJECT_STATUSES = frozenset({"delivered", "archived"})
COMPLETE_PROJECT_PHASES = frozenset({"delivery_complete", "delivered", "archived"})
ACTIVE_MINT_RECORD_STATUSES = frozenset(
    {
        "draft",
        "pending_approval",
        "approved",
        "queued",
        "processing",
        "minting",
        # A technical failure does not consume the customer's right to retry
        # the same paid mint. Keep the credit bound to the failed record so a
        # second checkout cannot be sold as the recovery mechanism.
        "failed",
    }
)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _now() -> datetime:
    return datetime.now(UTC)


def _db() -> Database:
    db = cast(Database | None, get_database())
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db


def _id_candidates(value: Any) -> list[Any]:
    normalized = _normalize(value)
    candidates: list[Any] = []
    if normalized:
        candidates.append(normalized)
    if ObjectId.is_valid(normalized):
        candidates.append(ObjectId(normalized))
    return list(dict.fromkeys(candidates))


def _project(project_id: str) -> dict[str, Any]:
    candidates = _id_candidates(project_id)
    if not candidates:
        raise ValueError("Project not found.")
    project = _db()["projects"].find_one({"_id": {"$in": candidates}})
    if not isinstance(project, dict):
        raise ValueError("Project not found.")
    return project


def profile_is_complete(project: dict[str, Any]) -> bool:
    status = _normalize(project.get("status")).lower()
    phase = _normalize(project.get("phase")).lower()
    return status in COMPLETE_PROJECT_STATUSES or phase in COMPLETE_PROJECT_PHASES


def purchase_runtime_is_ready(project: dict[str, Any]) -> bool:
    if not (
        settings.nft_mint_enabled
        and settings.nft_mint_worker_enabled
        and not settings.nft_auto_mint_on_review_enabled
    ):
        return False
    if (
        settings.is_production_environment
        and not settings.nft_legacy_payment_links_disabled
    ):
        return False
    package_code = _normalize(
        project.get("package_code")
        or project.get("package_slug")
        or project.get("package_type")
    )
    control_profile = get_package_control_profile(package_code) or {}
    token_type = _normalize((control_profile.get("mint_policy") or {}).get("token_type"))
    if token_type == "organization_anchor" and not settings.nft_org_mint_enabled:
        return False
    return True


def project_mint_count(project_id: str, project: dict[str, Any] | None = None) -> int:
    source = project or _project(project_id)
    token_ids = {
        _normalize(record.get("token_id"))
        for record in _db()["mint_records"].find(
            {
                "project_id": {"$in": _id_candidates(project_id)},
                "token_id": {"$exists": True, "$nin": [None, ""]},
            }
        )
        if _normalize(record.get("token_id"))
    }
    legacy_token_id = _normalize(source.get("mint_token_id"))
    if legacy_token_id:
        token_ids.add(legacy_token_id)
    if token_ids:
        return len(token_ids)
    # A legacy project may retain the transaction before its token id was
    # backfilled. Count it as one completed mint so it can never buy the first
    # mint product again.
    return 1 if _normalize(source.get("mint_tx_hash")) else 0


def project_has_existing_mint(project_id: str, project: dict[str, Any] | None = None) -> bool:
    return project_mint_count(project_id, project) > 0


def _credit_slot(project_id: str, addon_code: str, *, mint_count: int) -> tuple[str, str]:
    code = normalize_addon_code(addon_code)
    if code == INITIAL_MINT_ADDON_CODE:
        slot = "mint:1"
    elif code == ADDITIONAL_MINT_ADDON_CODE:
        slot = f"mint:{mint_count + 1}"
    else:
        return "", ""
    return slot, f"{_normalize(project_id)}:{slot}"


def _record_for_paid_credit(project_id: str) -> dict[str, Any] | None:
    record = _db()["mint_records"].find_one(
        {
            "project_id": {"$in": _id_candidates(project_id)},
            "mint_status": {"$in": list(ACTIVE_MINT_RECORD_STATUSES)},
            "nft_addon_order_id": {"$nin": [None, ""]},
        },
        sort=[("version_number", -1), ("updated_at", -1)],
    )
    return record if isinstance(record, dict) else None


def _active_mint_record(project_id: str) -> dict[str, Any] | None:
    return _record_for_paid_credit(project_id)


def _order_addon_code(order: dict[str, Any]) -> str:
    return normalize_addon_code(
        order.get("addon_code") or order.get("purchase_code") or order.get("package_code")
    )


def _paid_nft_addon_orders(project_id: str) -> list[dict[str, Any]]:
    orders = _db()["orders"].find(
        {
            "project_id": {"$in": _id_candidates(project_id)},
            "item_type": "addon",
            "source": {"$in": list(AUTHORITATIVE_ORDER_SOURCES)},
            "status": {"$in": list(PAID_ORDER_STATUSES)},
            "nft_addon_verified": True,
            "$or": [
                {"addon_code": {"$in": list(NFT_ADDON_CODES)}},
                {"package_code": {"$in": list(NFT_ADDON_CODES)}},
            ],
        }
    )
    return [order for order in orders if _order_addon_code(order) in NFT_ADDON_CODES]


def _credit_is_available(order: dict[str, Any]) -> bool:
    return _normalize(order.get("nft_credit_status")).lower() in {"", "available"}


def get_nft_addon_status(
    project_id: str,
    *,
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = project or _project(project_id)
    normalized_project_id = _normalize(source.get("_id") or source.get("id") or project_id)
    complete = profile_is_complete(source)
    purchase_runtime_ready = purchase_runtime_is_ready(source)
    mint_count = project_mint_count(normalized_project_id, source)
    existing_mint = mint_count > 0
    active_record = _active_mint_record(normalized_project_id)
    orders = _paid_nft_addon_orders(normalized_project_id)
    paid_order_ids = {_normalize(order.get("_id")) for order in orders}

    counts = {code: 0 for code in NFT_ADDON_CODES}
    available = {code: 0 for code in NFT_ADDON_CODES}
    consumed = {code: 0 for code in NFT_ADDON_CODES}
    for order in orders:
        code = _order_addon_code(order)
        counts[code] += 1
        if _credit_is_available(order):
            available[code] += 1
        else:
            consumed[code] += 1

    required_code = (
        ADDITIONAL_MINT_ADDON_CODE if existing_mint else INITIAL_MINT_ADDON_CODE
    )
    required_credit_slot, required_credit_slot_key = _credit_slot(
        normalized_project_id,
        required_code,
        mint_count=mint_count,
    )
    active_code = normalize_addon_code((active_record or {}).get("nft_addon_code"))
    active_order_id = _normalize((active_record or {}).get("nft_addon_order_id"))
    active_credit = bool(
        active_record
        and active_code in MINT_ADDON_CODES
        and active_order_id in paid_order_ids
    )
    available_required_credit = available.get(required_code, 0) > 0

    return {
        "project_id": normalized_project_id,
        "profile_complete": complete,
        "profile_completion_required": True,
        "purchase_runtime_ready": purchase_runtime_ready,
        "has_existing_mint": existing_mint,
        "mint_count": mint_count,
        "active_mint_record_id": _normalize((active_record or {}).get("_id")) or None,
        "active_mint_addon_code": active_code or None,
        "active_mint_credit": active_credit,
        "required_mint_addon_code": required_code,
        "required_mint_addon": get_addon(required_code),
        "required_mint_credit_slot": required_credit_slot,
        "required_mint_credit_slot_key": required_credit_slot_key,
        "mint_credit_satisfied": bool(active_credit or available_required_credit),
        "available_mint_credit_count": int(available.get(required_code, 0)),
        "purchased_counts": counts,
        "available_counts": available,
        "consumed_counts": consumed,
        "purchase_options": {
            INITIAL_MINT_ADDON_CODE: {
                "eligible": bool(
                    complete
                    and purchase_runtime_ready
                    and not existing_mint
                    and not active_credit
                    and available[INITIAL_MINT_ADDON_CODE] == 0
                ),
                "reason": (
                    None
                    if (
                        complete
                        and purchase_runtime_ready
                        and not existing_mint
                        and not active_credit
                        and available[INITIAL_MINT_ADDON_CODE] == 0
                    )
                    else "profile_not_complete"
                    if not complete
                    else "mint_runtime_unavailable"
                    if not purchase_runtime_ready
                    else "mint_credit_already_purchased"
                    if available[INITIAL_MINT_ADDON_CODE] > 0
                    else "initial_mint_already_exists_or_is_in_progress"
                ),
            },
            ADDITIONAL_MINT_ADDON_CODE: {
                "eligible": bool(
                    complete
                    and purchase_runtime_ready
                    and existing_mint
                    and not active_credit
                    and available[ADDITIONAL_MINT_ADDON_CODE] == 0
                ),
                "reason": (
                    None
                    if (
                        complete
                        and purchase_runtime_ready
                        and existing_mint
                        and not active_credit
                        and available[ADDITIONAL_MINT_ADDON_CODE] == 0
                    )
                    else "profile_not_complete"
                    if not complete
                    else "mint_runtime_unavailable"
                    if not purchase_runtime_ready
                    else "existing_mint_required"
                    if not existing_mint
                    else "mint_credit_already_purchased"
                    if available[ADDITIONAL_MINT_ADDON_CODE] > 0
                    else "mint_already_in_progress"
                ),
            },
            METADATA_REVISION_ADDON_CODE: {
                "eligible": bool(complete and purchase_runtime_ready and existing_mint),
                "reason": (
                    None
                    if complete and purchase_runtime_ready and existing_mint
                    else "profile_not_complete"
                    if not complete
                    else "mint_runtime_unavailable"
                    if not purchase_runtime_ready
                    else "existing_mint_required"
                ),
                "authorizes_new_mint": False,
            },
        },
        "checkout_never_triggers_mint": True,
    }


def _user_can_purchase_for_project(user: dict[str, Any], project: dict[str, Any]) -> bool:
    user_ids = _id_candidates(user.get("_id") or user.get("id") or user.get("user_id"))
    owner_ids = _id_candidates(project.get("owner_user_id"))
    if set(user_ids).intersection(owner_ids):
        return True

    user_email = _normalize(user.get("email")).lower()
    owner_email = _normalize(project.get("owner_email")).lower()
    if user_email and owner_email and user_email == owner_email:
        return True

    member = _db()["project_members"].find_one(
        {
            "project_id": {"$in": _id_candidates(project.get("_id"))},
            "user_id": {"$in": user_ids},
            "status": {"$in": ["active", "accepted"]},
            "role": {"$in": ["billing_owner", "co_owner"]},
        }
    )
    return isinstance(member, dict)


def validate_nft_addon_purchase_target(
    *,
    user: dict[str, Any],
    project_id: str,
    addon_code: str,
) -> dict[str, Any]:
    code = normalize_addon_code(addon_code)
    if code not in NFT_ADDON_CODES:
        raise ValueError("Checkout product is not a recognized NFT add-on.")
    project = _project(project_id)
    if not _user_can_purchase_for_project(user, project):
        raise ValueError("NFT add-on checkout does not belong to this customer workspace.")
    if not profile_is_complete(project):
        raise ValueError("Complete the customer profile before purchasing an NFT add-on.")
    if not purchase_runtime_is_ready(project):
        raise ValueError("NFT add-on checkout is temporarily unavailable until mint operations are ready.")

    status = get_nft_addon_status(project_id, project=project)
    option = dict((status.get("purchase_options") or {}).get(code) or {})
    if not option.get("eligible"):
        reason = _normalize(option.get("reason")) or "nft_addon_not_available"
        messages = {
            "mint_credit_already_purchased": (
                "The required NFT mint add-on is already paid for this mint."
            ),
            "initial_mint_already_exists_or_is_in_progress": (
                "Use Additional NFT Copy / Mint after the first NFT has been minted."
            ),
            "existing_mint_required": (
                "The first NFT must be minted before purchasing this add-on."
            ),
            "mint_already_in_progress": (
                "The current paid NFT mint must finish or be reconciled before another purchase."
            ),
        }
        raise ValueError(messages.get(reason, "This NFT add-on is not available for the current project state."))

    validated = dict(project)
    if code in MINT_ADDON_CODES:
        slot, slot_key = _credit_slot(
            _normalize(project.get("_id") or project_id),
            code,
            mint_count=int(status.get("mint_count") or 0),
        )
        validated["_nft_credit_slot"] = slot
        validated["_nft_credit_slot_key"] = slot_key
    else:
        purchased_count = int(
            ((status.get("purchased_counts") or {}).get(code)) or 0
        )
        validated["_nft_checkout_sequence"] = f"revision:{purchased_count + 1}"
    return validated


def reserve_paid_mint_addon(
    project_id: str,
    *,
    required_addon_code: str,
) -> dict[str, Any]:
    code = normalize_addon_code(required_addon_code)
    if code not in MINT_ADDON_CODES:
        raise ValueError("A mint-authorizing NFT add-on is required.")

    claim_token = secrets.token_urlsafe(24)
    orders: Collection[dict[str, Any]] = _db()["orders"]
    order = orders.find_one_and_update(
        {
            "project_id": {"$in": _id_candidates(project_id)},
            "item_type": "addon",
            "source": {"$in": list(AUTHORITATIVE_ORDER_SOURCES)},
            "status": {"$in": list(PAID_ORDER_STATUSES)},
            "nft_addon_verified": True,
            "$or": [{"addon_code": code}, {"package_code": code}],
            "nft_credit_status": {"$in": [None, "", "available"]},
        },
        {
            "$set": {
                "nft_credit_status": "reserved",
                "nft_credit_claim_token": claim_token,
                "nft_credit_reserved_at": _now(),
                "updated_at": _now(),
            }
        },
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    if not isinstance(order, dict):
        raise ValueError(f"A paid {code.replace('_', ' ')} add-on is required before preparation.")
    return {
        "order_id": _normalize(order.get("_id")),
        "addon_code": code,
        "claim_token": claim_token,
    }


def finalize_mint_addon_reservation(
    reservation: dict[str, Any],
    *,
    mint_record_id: str,
) -> None:
    order_id = _normalize(reservation.get("order_id"))
    claim_token = _normalize(reservation.get("claim_token"))
    if not ObjectId.is_valid(order_id) or not claim_token:
        raise ValueError("NFT add-on reservation is invalid.")
    result = _db()["orders"].update_one(
        {"_id": ObjectId(order_id), "nft_credit_claim_token": claim_token},
        {
            "$set": {
                "nft_credit_status": "claimed",
                "nft_credit_mint_record_id": (
                    ObjectId(mint_record_id)
                    if ObjectId.is_valid(mint_record_id)
                    else mint_record_id
                ),
                "nft_credit_claimed_at": _now(),
                "updated_at": _now(),
            },
            "$unset": {"nft_credit_claim_token": ""},
        },
    )
    if not result.modified_count:
        raise RuntimeError("NFT add-on reservation could not be finalized.")


def release_mint_addon_reservation(reservation: dict[str, Any]) -> None:
    order_id = _normalize(reservation.get("order_id"))
    claim_token = _normalize(reservation.get("claim_token"))
    if not ObjectId.is_valid(order_id) or not claim_token:
        return
    _db()["orders"].update_one(
        {"_id": ObjectId(order_id), "nft_credit_claim_token": claim_token},
        {
            "$set": {"nft_credit_status": "available", "updated_at": _now()},
            "$unset": {
                "nft_credit_claim_token": "",
                "nft_credit_reserved_at": "",
            },
        },
    )
