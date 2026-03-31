from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from app.config import settings
from app.core.package_catalog import get_package
from app.database import get_database
from app.services.mint_policy_service import get_package_mint_policy
from app.services.public_manifest_service import (
    build_public_manifest,
    compute_build_hash,
    compute_certificate_hash,
    compute_household_ref_hash,
    compute_project_ref_hash,
    ensure_public_manifest_indexes,
    get_public_manifest_for_mint_record,
)

ADMIN_APPROVAL_TYPE = "admin_final"
CUSTOMER_APPROVAL_TYPE = "customer_public_safe"
ACTIVE_MINT_RECORD_STATUSES = {"pending_approval", "approved", "queued", "minting"}


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_tx_hash(value: Any) -> str | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    return normalized if normalized.lower().startswith("0x") else f"0x{normalized}"


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _records_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_records"])


def _approvals_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_approvals"])


def _projects_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["projects"])


def ensure_mint_record_indexes() -> None:
    records = _records_collection()
    approvals = _approvals_collection()

    record_definitions = [
        ([("project_id", 1), ("version_number", -1)], "project_id_1_version_number_-1"),
        ([("mint_status", 1), ("created_at", -1)], "mint_status_1_created_at_-1"),
        ([("tx_hash", 1)], "tx_hash_1"),
        ([("token_id", 1), ("contract_address", 1)], "token_id_1_contract_address_1"),
    ]
    approval_definitions = [
        ([("project_id", 1), ("approval_type", 1), ("status", 1)], "project_id_1_approval_type_1_status_1"),
        ([("mint_record_id", 1)], "mint_record_id_1"),
    ]

    existing_record_indexes = records.index_information()
    for keys, name in record_definitions:
        if name in existing_record_indexes:
            continue
        try:
            records.create_index(keys, name=name)
        except OperationFailure:
            continue

    existing_approval_indexes = approvals.index_information()
    for keys, name in approval_definitions:
        if name in existing_approval_indexes:
            continue
        try:
            approvals.create_index(keys, name=name)
        except OperationFailure:
            continue

    ensure_public_manifest_indexes()


def _project_document(project_id: str) -> dict[str, Any]:
    oid = _to_object_id(project_id)
    if oid is None:
        raise ValueError("Project not found.")

    project = _projects_collection().find_one({"_id": oid})
    if project is None:
        raise ValueError("Project not found.")
    return project


def _package_fields(project: dict[str, Any]) -> tuple[str, str]:
    package = get_package(
        _normalize(
            project.get("package_code")
            or project.get("package_slug")
            or project.get("package_type")
        )
    )
    if not package:
        return (
            _normalize(project.get("package_code") or project.get("package_slug")),
            _normalize(project.get("project_lane")),
        )
    return (
        _normalize(package.get("package_code")),
        _normalize(package.get("package_lane")),
    )


def _requires_customer_approval(
    policy: dict[str, Any],
    *,
    poster_style: str,
    public_title_opt_in: bool,
    customer_wallet: str | None = None,
) -> bool:
    return bool(
        policy.get("requires_customer_public_safe_approval")
        or _normalize(poster_style).lower() == "approved_poster"
        or public_title_opt_in
        or _normalize(customer_wallet)
    )


def _serialize_record(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize(document.get("_id")),
        "project_id": _normalize(document.get("project_id")),
        "household_id": _normalize(document.get("household_id")) or None,
        "family_id": _normalize(document.get("family_id")) or None,
        "user_id": _normalize(document.get("user_id")),
        "package_code": _normalize(document.get("package_code")),
        "package_lane": _normalize(document.get("package_lane")),
        "token_type": _normalize(document.get("token_type")) or None,
        "chain": _normalize(document.get("chain")) or settings.nft_chain,
        "contract_address": _normalize(document.get("contract_address"))
        or settings.nft_contract_address,
        "token_id": _normalize(document.get("token_id")) or None,
        "tx_hash": _normalize(document.get("tx_hash")) or None,
        "metadata_uri": _normalize(document.get("metadata_uri")),
        "project_ref_hash": _normalize(document.get("project_ref_hash")),
        "household_ref_hash": _normalize(document.get("household_ref_hash")) or None,
        "build_hash": _normalize(document.get("build_hash")),
        "certificate_hash": _normalize(document.get("certificate_hash")) or None,
        "version_number": int(document.get("version_number") or 1),
        "poster_image_uri_public": _normalize(document.get("poster_image_uri_public")),
        "poster_style": _normalize(document.get("poster_style")) or "abstract_cover",
        "mint_status": _normalize(document.get("mint_status")) or "pending_approval",
        "approved_at": document.get("approved_at"),
        "minted_at": document.get("minted_at"),
        "failed_at": document.get("failed_at"),
        "customer_wallet": _normalize(document.get("customer_wallet")) or None,
        "minted_by": _normalize(document.get("minted_by")) or None,
        "public_title_opt_in": bool(document.get("public_title_opt_in")),
        "public_title": _normalize(document.get("public_title")) or None,
        "public_title_kind": _normalize(document.get("public_title_kind")) or "none",
        "error_code": _normalize(document.get("error_code")) or None,
        "error_message": _normalize(document.get("error_message")) or None,
        "pending_approvals": list_pending_approvals(
            _normalize(document.get("_id"))
        ),
        "created_at": document.get("created_at") or _now(),
        "updated_at": document.get("updated_at") or _now(),
    }


def get_mint_record(mint_record_id: str) -> dict[str, Any] | None:
    oid = _to_object_id(mint_record_id)
    if oid is None:
        return None
    document = _records_collection().find_one({"_id": oid})
    if document is None:
        return None
    return _serialize_record(document)


def get_latest_mint_record(project_id: str) -> dict[str, Any] | None:
    document = _records_collection().find_one(
        {"project_id": _normalize(project_id)},
        sort=[("version_number", -1), ("created_at", -1)],
    )
    if document is None:
        return None
    return _serialize_record(document)


def list_mint_records(project_id: str) -> list[dict[str, Any]]:
    cursor = _records_collection().find({"project_id": _normalize(project_id)}).sort(
        [("version_number", -1), ("created_at", -1)]
    )
    return [_serialize_record(document) for document in cursor]


def list_pending_approvals(mint_record_id: str) -> list[str]:
    cursor = _approvals_collection().find(
        {"mint_record_id": _normalize(mint_record_id), "status": "pending"}
    )
    return [_normalize(document.get("approval_type")) for document in cursor]


def _ensure_approval_record(
    *,
    project_id: str,
    mint_record_id: str,
    approval_type: str,
    status: str = "pending",
    approved_by_user_id: str | None = None,
    approved_by_email: str | None = None,
    notes: str | None = None,
    consent_snapshot: dict[str, Any] | None = None,
) -> None:
    now = _now()
    query = {
        "project_id": _normalize(project_id),
        "mint_record_id": _normalize(mint_record_id),
        "approval_type": _normalize(approval_type),
    }
    existing = _approvals_collection().find_one(query)
    document = {
        "project_id": _normalize(project_id),
        "mint_record_id": _normalize(mint_record_id),
        "approval_type": _normalize(approval_type),
        "status": _normalize(status) or "pending",
        "approved_by_user_id": _normalize(approved_by_user_id) or None,
        "approved_by_email": _normalize(approved_by_email) or None,
        "notes": _normalize(notes) or None,
        "consent_snapshot": consent_snapshot or {},
        "updated_at": now,
    }

    if existing is None:
        document["created_at"] = now
        _approvals_collection().insert_one(document)
    else:
        _approvals_collection().update_one({"_id": existing["_id"]}, {"$set": document})


def _delete_approval_record(mint_record_id: str, approval_type: str) -> None:
    _approvals_collection().delete_many(
        {
            "mint_record_id": _normalize(mint_record_id),
            "approval_type": _normalize(approval_type),
        }
    )


def _refresh_manifest(mint_record_id: str, approval_timestamp: datetime | None = None) -> None:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")

    manifest = build_public_manifest(
        record["project_id"],
        record["version_number"],
        mint_record_id=mint_record_id,
        poster_style=record["poster_style"],
        public_title_opt_in=bool(record["public_title_opt_in"]),
        public_title=record.get("public_title"),
        public_title_kind=record.get("public_title_kind") or "none",
        approved_poster_opt_in=record["poster_style"] == "approved_poster",
        approval_timestamp=approval_timestamp,
    )

    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "metadata_uri": manifest["metadata_uri"],
                "poster_image_uri_public": manifest["poster_image_uri_public"],
                "build_hash": manifest["build_hash"],
                "certificate_hash": manifest["certificate_hash"],
                "updated_at": _now(),
            }
        },
    )


def _supersede_active_records(
    project_id: str,
    *,
    keep_mint_record_id: str = "",
) -> None:
    query: dict[str, Any] = {
        "project_id": _normalize(project_id),
        "mint_status": {"$in": list(ACTIVE_MINT_RECORD_STATUSES)},
    }
    keep_oid = _to_object_id(keep_mint_record_id)
    if keep_oid is not None:
        query["_id"] = {"$ne": keep_oid}

    _records_collection().update_many(
        query,
        {
            "$set": {
                "mint_status": "superseded",
                "updated_at": _now(),
            }
        },
    )


def _next_version_number(project_id: str) -> int:
    latest = get_latest_mint_record(project_id)
    return int((latest or {}).get("version_number") or 0) + 1


def create_mint_record(
    project_id: str,
    *,
    version_strategy: str = "new_version_if_needed",
    poster_style: str = "abstract_cover",
    public_title_opt_in: bool = False,
    public_title: str | None = None,
    public_title_kind: str = "none",
) -> dict[str, Any]:
    project = _project_document(project_id)
    package_code, package_lane = _package_fields(project)
    policy = get_package_mint_policy(package_code)

    if not policy.get("product_includes_onchain_anchor"):
        raise ValueError("This package does not include an on-chain legacy anchor.")

    existing = get_latest_mint_record(project_id)
    if (
        version_strategy == "new_version_if_needed"
        and existing is not None
        and existing.get("mint_status") in ACTIVE_MINT_RECORD_STATUSES
    ):
        return existing

    version_number = _next_version_number(project_id)
    project_doc_id = _normalize(project.get("_id"))
    now = _now()

    document: dict[str, Any] = {
        "project_id": project_doc_id,
        "household_id": _normalize(project.get("household_id")) or None,
        "family_id": _normalize(project.get("family_id")) or None,
        "user_id": _normalize(project.get("owner_user_id")),
        "package_code": package_code,
        "package_lane": package_lane,
        "token_type": _normalize(policy.get("token_type")) or None,
        "chain": settings.nft_chain,
        "contract_address": settings.nft_contract_address,
        "token_id": None,
        "tx_hash": None,
        "metadata_uri": "",
        "project_ref_hash": compute_project_ref_hash(project_doc_id),
        "household_ref_hash": compute_household_ref_hash(project.get("household_id")),
        "build_hash": compute_build_hash(project_doc_id),
        "certificate_hash": compute_certificate_hash(project_doc_id),
        "version_number": version_number,
        "poster_image_uri_public": "",
        "poster_style": _normalize(poster_style).lower() or "abstract_cover",
        "mint_status": "pending_approval",
        "approved_at": None,
        "minted_at": None,
        "failed_at": None,
        "customer_wallet": None,
        "minted_by": None,
        "public_title_opt_in": bool(public_title_opt_in),
        "public_title": _normalize(public_title) or None,
        "public_title_kind": _normalize(public_title_kind) or "none",
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }

    result = _records_collection().insert_one(document)
    mint_record_id = _normalize(result.inserted_id)
    _supersede_active_records(project_doc_id, keep_mint_record_id=mint_record_id)

    _ensure_approval_record(
        project_id=project_doc_id,
        mint_record_id=mint_record_id,
        approval_type=ADMIN_APPROVAL_TYPE,
        status="pending",
    )

    if _requires_customer_approval(
        policy,
        poster_style=document["poster_style"],
        public_title_opt_in=bool(document["public_title_opt_in"]),
    ):
        _ensure_approval_record(
            project_id=project_doc_id,
            mint_record_id=mint_record_id,
            approval_type=CUSTOMER_APPROVAL_TYPE,
            status="pending",
            consent_snapshot={
                "public_title_opt_in": bool(document["public_title_opt_in"]),
                "approved_poster_opt_in": document["poster_style"] == "approved_poster",
                "wallet_address": None,
            },
        )

    _refresh_manifest(mint_record_id)
    return get_mint_record(mint_record_id) or _serialize_record(document)


def _recompute_mint_approval_state(mint_record_id: str) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")

    pending = list_pending_approvals(mint_record_id)
    approved_at = record.get("approved_at")
    next_status = "approved" if not pending else "pending_approval"

    if next_status == "approved" and approved_at is None:
        approved_at = _now()

    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "mint_status": next_status,
                "approved_at": approved_at,
                "updated_at": _now(),
            }
        },
    )
    _refresh_manifest(mint_record_id, approval_timestamp=approved_at)
    updated = get_mint_record(mint_record_id)
    if updated is None:
        raise ValueError("Mint record not found.")
    return updated


def approve_admin_mint_record(
    mint_record_id: str,
    *,
    approved_by_email: str,
    notes: str = "",
) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")

    _ensure_approval_record(
        project_id=record["project_id"],
        mint_record_id=mint_record_id,
        approval_type=ADMIN_APPROVAL_TYPE,
        status="approved",
        approved_by_email=approved_by_email,
        notes=notes,
    )
    return _recompute_mint_approval_state(mint_record_id)


def approve_customer_mint_record(
    mint_record_id: str,
    *,
    approved_by_user_id: str,
    approved_by_email: str,
    notes: str = "",
    wallet_address: str | None = None,
    approved_poster_opt_in: bool = False,
    public_title_opt_in: bool = False,
    public_title: str | None = None,
    public_title_kind: str = "none",
) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")

    next_poster_style = record["poster_style"]
    if next_poster_style == "approved_poster" and not approved_poster_opt_in:
        next_poster_style = "abstract_cover"

    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "customer_wallet": _normalize(wallet_address) or None,
                "poster_style": next_poster_style,
                "public_title_opt_in": bool(public_title_opt_in),
                "public_title": _normalize(public_title) or None,
                "public_title_kind": _normalize(public_title_kind) or "none",
                "updated_at": _now(),
            }
        },
    )

    _ensure_approval_record(
        project_id=record["project_id"],
        mint_record_id=mint_record_id,
        approval_type=CUSTOMER_APPROVAL_TYPE,
        status="approved",
        approved_by_user_id=approved_by_user_id,
        approved_by_email=approved_by_email,
        notes=notes,
        consent_snapshot={
            "public_title_opt_in": bool(public_title_opt_in),
            "approved_poster_opt_in": bool(approved_poster_opt_in),
            "wallet_address": _normalize(wallet_address) or None,
        },
    )
    return _recompute_mint_approval_state(mint_record_id)


def mark_mint_queued(mint_record_id: str) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")
    if record["mint_status"] not in {"approved", "queued"}:
        raise ValueError("Mint record must be approved before queueing.")

    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {"$set": {"mint_status": "queued", "updated_at": _now()}},
    )
    updated = get_mint_record(mint_record_id)
    if updated is None:
        raise ValueError("Mint record not found.")
    return updated


def mark_mint_minting(mint_record_id: str, *, tx_hash: str | None = None) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")

    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "mint_status": "minting",
                "tx_hash": _normalize_tx_hash(tx_hash) or record.get("tx_hash"),
                "failed_at": None,
                "error_code": None,
                "error_message": None,
                "updated_at": _now(),
            }
        },
    )
    updated = get_mint_record(mint_record_id)
    if updated is None:
        raise ValueError("Mint record not found.")
    return updated


def mark_mint_minted(
    mint_record_id: str,
    *,
    token_id: str,
    tx_hash: str,
    minted_by: str = "system",
    contract_address: str | None = None,
    chain: str | None = None,
) -> dict[str, Any]:
    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "mint_status": "minted",
                "token_id": _normalize(token_id),
                "tx_hash": _normalize_tx_hash(tx_hash),
                "minted_by": _normalize(minted_by) or "system",
                "contract_address": _normalize(contract_address) or settings.nft_contract_address,
                "chain": _normalize(chain) or settings.nft_chain,
                "minted_at": _now(),
                "failed_at": None,
                "error_code": None,
                "error_message": None,
                "updated_at": _now(),
            }
        },
    )
    _supersede_active_records(
        _normalize((get_mint_record(mint_record_id) or {}).get("project_id")),
        keep_mint_record_id=mint_record_id,
    )
    updated = get_mint_record(mint_record_id)
    if updated is None:
        raise ValueError("Mint record not found.")
    return updated


def mark_mint_failed(
    mint_record_id: str,
    *,
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "mint_status": "failed",
                "failed_at": _now(),
                "error_code": _normalize(error_code) or "mint_failed",
                "error_message": _normalize(error_message) or "Mint job failed.",
                "updated_at": _now(),
            }
        },
    )
    updated = get_mint_record(mint_record_id)
    if updated is None:
        raise ValueError("Mint record not found.")
    return updated


def build_mint_status(project_id: str) -> dict[str, Any]:
    project = _project_document(project_id)
    package_code, _package_lane = _package_fields(project)
    history = list_mint_records(project_id)
    latest = history[0] if history else None
    manifest = (
        get_public_manifest_for_mint_record(latest["id"])
        if latest is not None
        else None
    )
    mint_policy = get_package_mint_policy(package_code)

    if latest is not None and manifest is not None:
        latest = {
            **latest,
            "metadata_uri": manifest["metadata_uri"],
            "poster_image_uri_public": manifest["poster_image_uri_public"],
        }

    return {
        "project_id": _normalize(project_id),
        "mint_enabled": bool(mint_policy.get("product_includes_onchain_anchor")),
        "latest": latest,
        "history": history,
    }
