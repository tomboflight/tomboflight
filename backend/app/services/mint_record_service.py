from __future__ import annotations

import re
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
MINT_RECORD_LIFECYCLE_STATUSES = {
    "draft",
    "pending_approval",
    "approved",
    "queued",
    "processing",
    "minting",
    "minted",
    "failed",
    "superseded",
    "canceled",
    "cancelled",
}
CANONICAL_MINT_RECORD_STATUS_ALIASES = {
    "pending_approval": "draft",
    "minting": "processing",
    "cancelled": "canceled",
}
ACTIVE_MINT_RECORD_STATUSES = {"draft", "pending_approval", "approved", "queued", "processing", "minting"}
NON_AUTHORITATIVE_MINT_RECORD_STATUSES = {"superseded", "canceled", "cancelled"}
MINTED_MINT_RECORD_STATUSES = {"minted"}
FAILED_MINT_RECORD_STATUSES = {"failed"}
CURRENT_MINT_RECORD_PRECEDENCE = {
    "minted": 0,
    "processing": 1,
    "queued": 1,
    "approved": 1,
    "draft": 1,
    "failed": 2,
    "superseded": 3,
    "canceled": 3,
}
ACTIVE_MINT_JOB_STATUSES = {"queued", "locked", "started", "running"}
OBSOLETE_MINT_JOB_STATUSES = {"obsolete", "canceled", "cancelled"}
REQUEUE_VERSION_STRATEGIES = {"new_version", "force_new_version", "always_new"}
EVM_WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
HEX_PRIVATE_KEY_PATTERN = re.compile(r"^(0x)?[a-fA-F0-9]{64}$")


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_tx_hash(value: Any) -> str | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    if not normalized.lower().startswith("0x"):
        normalized = f"0x{normalized}"
    return normalized.lower()


def _normalize_wallet_address(wallet_address: str | None, *, required: bool = False) -> str | None:
    normalized = _normalize(wallet_address)
    if not normalized:
        if required:
            raise ValueError("A valid recipient wallet address is required.")
        return None

    lowered = normalized.lower()
    if "wallet_address" in lowered or "customer_wallet" in lowered:
        raise ValueError("Placeholder wallet values are not allowed.")
    if HEX_PRIVATE_KEY_PATTERN.fullmatch(normalized) and len(normalized.removeprefix("0x")) == 64:
        raise ValueError("A wallet address is required. Private keys are not accepted here.")
    if not EVM_WALLET_PATTERN.fullmatch(normalized):
        raise ValueError("Wallet address must be a valid EVM address starting with 0x.")
    return f"0x{normalized[2:].lower()}"


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _id_candidates(value: Any) -> list[Any]:
    normalized = _normalize(value)
    candidates: list[Any] = []
    if normalized:
        candidates.append(normalized)
    oid = _to_object_id(normalized)
    if oid is not None:
        candidates.append(oid)
    return list(dict.fromkeys(candidates))


def _object_id_or_text(value: Any) -> ObjectId | str | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    oid = _to_object_id(normalized)
    return oid if oid is not None else normalized


def _canonical_record_status(value: Any) -> str:
    normalized = _normalize(value).lower() or "draft"
    return CANONICAL_MINT_RECORD_STATUS_ALIASES.get(normalized, normalized)


def _status_precedence(value: Any) -> int:
    return CURRENT_MINT_RECORD_PRECEDENCE.get(_canonical_record_status(value), 4)


def _record_timestamp(document: dict[str, Any]) -> datetime:
    for key in ("minted_at", "updated_at", "created_at", "failed_at"):
        value = document.get(key)
        if isinstance(value, datetime):
            return value
    return datetime.min.replace(tzinfo=UTC)


def _record_time_rank(document: dict[str, Any]) -> int:
    value = _record_timestamp(document)
    return (
        value.toordinal() * 86_400_000_000
        + value.hour * 3_600_000_000
        + value.minute * 60_000_000
        + value.second * 1_000_000
        + value.microsecond
    )


def _records_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_records"])


def _jobs_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_jobs"])


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
    project = _projects_collection().find_one({"_id": {"$in": _id_candidates(project_id)}})
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
    mint_status = _normalize(document.get("mint_status")) or "pending_approval"
    canonical_status = _canonical_record_status(mint_status)
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
        "tx_hash": _normalize_tx_hash(document.get("tx_hash")),
        "metadata_uri": _normalize(document.get("metadata_uri")),
        "project_ref_hash": _normalize(document.get("project_ref_hash")),
        "household_ref_hash": _normalize(document.get("household_ref_hash")) or None,
        "build_hash": _normalize(document.get("build_hash")),
        "certificate_hash": _normalize(document.get("certificate_hash")) or None,
        "version_number": int(document.get("version_number") or 1),
        "poster_image_uri_public": _normalize(document.get("poster_image_uri_public")),
        "poster_style": _normalize(document.get("poster_style")) or "abstract_cover",
        "mint_status": mint_status,
        "canonical_mint_status": canonical_status,
        "status_precedence": _status_precedence(mint_status),
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
    candidates = _id_candidates(mint_record_id)
    if not candidates:
        return None
    document = _records_collection().find_one({"_id": {"$in": candidates}})
    if document is None:
        return None
    return _serialize_record(document)


def _project_record_documents(project_id: str) -> list[dict[str, Any]]:
    return list(
        _records_collection()
        .find({"project_id": {"$in": _id_candidates(project_id)}})
        .sort([("version_number", -1), ("updated_at", -1), ("created_at", -1)])
    )


def _canonical_record_document(project_id: str) -> dict[str, Any] | None:
    records = _project_record_documents(project_id)
    if not records:
        return None
    return sorted(
        records,
        key=lambda document: (
            _status_precedence(document.get("mint_status")),
            -int(document.get("version_number") or 0),
            -_record_time_rank(document),
        ),
    )[0]


def get_latest_mint_record(project_id: str) -> dict[str, Any] | None:
    document = _canonical_record_document(project_id)
    if document is None:
        return None
    return _serialize_record(document)


def list_mint_records(project_id: str) -> list[dict[str, Any]]:
    return [_serialize_record(document) for document in _project_record_documents(project_id)]


def _record_with_manifest(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    manifest = get_public_manifest_for_mint_record(record["id"])
    if manifest is None:
        return record
    return {
        **record,
        "public_token_id": manifest["public_token_id"],
        "metadata_uri": manifest["metadata_uri"],
        "poster_image_uri_public": manifest["poster_image_uri_public"],
        "public_payload": manifest["payload"],
    }


def resolve_canonical_mint_status(
    project_id: str,
    *,
    include_history: bool = True,
) -> dict[str, Any]:
    records = [_serialize_record(document) for document in _project_record_documents(project_id)]
    current = get_latest_mint_record(project_id)
    current = _record_with_manifest(current)
    current_status = _canonical_record_status((current or {}).get("mint_status"))
    if current is None:
        current_status = "none"

    is_current_failed = current_status == "failed"
    current_error_code = current.get("error_code") if current and is_current_failed else None
    current_error_message = current.get("error_message") if current and is_current_failed else None

    historical_attempts = []
    for record in records:
        record_id = record.get("id")
        is_current = bool(current and record_id == current.get("id"))
        historical_attempts.append(
            {
                **record,
                "is_current": is_current,
                "is_historical": not is_current,
                "current_reason": "canonical_precedence" if is_current else "historical_attempt",
            }
        )

    return {
        "project_id": _normalize(project_id),
        "current_status": current_status,
        "canonical_status": current_status,
        "current_mint_record_id": (current or {}).get("id"),
        "current_record": current,
        "latest": current,
        "is_minted": current_status == "minted",
        "is_current_failed": is_current_failed,
        "token_id": (current or {}).get("token_id"),
        "tx_hash": (current or {}).get("tx_hash"),
        "chain": (current or {}).get("chain") or settings.nft_chain,
        "contract_address": (current or {}).get("contract_address") or settings.nft_contract_address,
        "version_number": (current or {}).get("version_number"),
        "wallet": (current or {}).get("customer_wallet"),
        "error_code": current_error_code,
        "error_message": current_error_message,
        "history": historical_attempts if include_history else [],
        "historical_attempt_count": max(0, len(records) - (1 if current else 0)),
    }


def mark_obsolete_mint_jobs_for_project(
    project_id: str,
    *,
    current_mint_record_id: str = "",
    reason: str = "canonical_mint_record_resolved",
) -> dict[str, Any]:
    now = _now()
    project_candidates = _id_candidates(project_id)
    current_record_id = _normalize(current_mint_record_id)
    job_query: dict[str, Any] = {
        "project_id": {"$in": project_candidates},
        "status": {"$in": list(ACTIVE_MINT_JOB_STATUSES)},
    }
    if current_record_id:
        job_query["mint_record_id"] = {"$nin": _id_candidates(current_record_id)}

    obsolete_prior = _jobs_collection().update_many(
        job_query,
        {
            "$set": {
                "status": "obsolete",
                "finished_at": now,
                "updated_at": now,
                "error_code": reason,
                "error_message": "Mint job belongs to a historical mint record.",
            }
        },
    )

    obsolete_current = 0
    if current_record_id:
        result = _jobs_collection().update_many(
            {
                "project_id": {"$in": project_candidates},
                "mint_record_id": {"$in": _id_candidates(current_record_id)},
                "status": {"$in": list(ACTIVE_MINT_JOB_STATUSES)},
            },
            {
                "$set": {
                    "status": "obsolete",
                    "finished_at": now,
                    "updated_at": now,
                    "error_code": "mint_already_completed",
                    "error_message": "Canonical mint record is already minted.",
                }
            },
        )
        obsolete_current = int(result.modified_count)

    return {
        "project_id": _normalize(project_id),
        "current_mint_record_id": current_record_id or None,
        "obsolete_prior_jobs": int(obsolete_prior.modified_count),
        "obsolete_current_jobs": obsolete_current,
    }


def normalize_mint_reference_ids_for_project(project_id: str) -> dict[str, Any]:
    project_candidates = _id_candidates(project_id)
    normalized_project_id = _object_id_or_text(project_id)
    summary = {
        "project_id": _normalize(project_id),
        "mint_records_updated": 0,
        "mint_jobs_updated": 0,
        "mint_approvals_updated": 0,
    }
    if normalized_project_id is None:
        return summary

    record_ids: list[str] = []
    for record in _records_collection().find({"project_id": {"$in": project_candidates}}):
        record_ids.append(_normalize(record.get("_id")))
        updates: dict[str, Any] = {}
        if not isinstance(record.get("project_id"), ObjectId):
            updates["project_id"] = normalized_project_id
        user_id = _object_id_or_text(record.get("user_id"))
        if user_id is not None and not isinstance(record.get("user_id"), ObjectId):
            updates["user_id"] = user_id
        if updates:
            updates["updated_at"] = _now()
            _records_collection().update_one({"_id": record["_id"]}, {"$set": updates})
            summary["mint_records_updated"] += 1

    record_id_candidates: list[Any] = []
    for record_id in record_ids:
        record_id_candidates.extend(_id_candidates(record_id))
    record_id_candidates = list(dict.fromkeys(record_id_candidates))

    job_filter: dict[str, Any] = {"project_id": {"$in": project_candidates}}
    if record_id_candidates:
        job_filter = {
            "$or": [
                {"project_id": {"$in": project_candidates}},
                {"mint_record_id": {"$in": record_id_candidates}},
            ]
        }
    for job in _jobs_collection().find(job_filter):
        updates = {}
        if not isinstance(job.get("project_id"), ObjectId):
            updates["project_id"] = normalized_project_id
        mint_record_id = _object_id_or_text(job.get("mint_record_id"))
        if mint_record_id is not None and not isinstance(job.get("mint_record_id"), ObjectId):
            updates["mint_record_id"] = mint_record_id
        if updates:
            updates["updated_at"] = _now()
            _jobs_collection().update_one({"_id": job["_id"]}, {"$set": updates})
            summary["mint_jobs_updated"] += 1

    approval_filter: dict[str, Any] = {"project_id": {"$in": project_candidates}}
    if record_id_candidates:
        approval_filter = {
            "$or": [
                {"project_id": {"$in": project_candidates}},
                {"mint_record_id": {"$in": record_id_candidates}},
            ]
        }
    for approval in _approvals_collection().find(approval_filter):
        updates = {}
        if not isinstance(approval.get("project_id"), ObjectId):
            updates["project_id"] = normalized_project_id
        mint_record_id = _object_id_or_text(approval.get("mint_record_id"))
        if mint_record_id is not None and not isinstance(approval.get("mint_record_id"), ObjectId):
            updates["mint_record_id"] = mint_record_id
        approved_by_user_id = _object_id_or_text(approval.get("approved_by_user_id"))
        if approved_by_user_id is not None and not isinstance(approval.get("approved_by_user_id"), ObjectId):
            updates["approved_by_user_id"] = approved_by_user_id
        if updates:
            updates["updated_at"] = _now()
            _approvals_collection().update_one({"_id": approval["_id"]}, {"$set": updates})
            summary["mint_approvals_updated"] += 1

    return summary


def rebuild_mint_summary_for_project(project_id: str) -> dict[str, Any]:
    id_normalization = normalize_mint_reference_ids_for_project(project_id)
    summary = resolve_canonical_mint_status(project_id, include_history=True)
    current = summary.get("current_record") or {}
    current_id = _normalize(current.get("id"))
    cleanup = {"obsolete_prior_jobs": 0, "obsolete_current_jobs": 0}
    now = _now()
    current_status = _normalize(summary.get("current_status")) or "none"
    project_updates: dict[str, Any] = {
        "mint_status": current_status,
        "canonical_mint_status": current_status,
        "current_mint_record_id": current_id or None,
        "mint_record_id": current_id or None,
        "mint_record_version": current.get("version_number"),
        "mint_token_id": summary.get("token_id"),
        "mint_tx_hash": summary.get("tx_hash"),
        "mint_chain": summary.get("chain") or settings.nft_chain,
        "mint_contract_address": summary.get("contract_address") or settings.nft_contract_address,
        "mint_wallet": summary.get("wallet"),
        "mint_error_code": summary.get("error_code"),
        "mint_error_message": summary.get("error_message"),
        "mint_historical_attempt_count": summary.get("historical_attempt_count", 0),
        "mint_summary": {
            "current_status": current_status,
            "current_mint_record_id": current_id or None,
            "token_id": summary.get("token_id"),
            "tx_hash": summary.get("tx_hash"),
            "chain": summary.get("chain") or settings.nft_chain,
            "version_number": summary.get("version_number"),
            "historical_attempt_count": summary.get("historical_attempt_count", 0),
            "is_current_failed": bool(summary.get("is_current_failed")),
        },
        "mint_summary_updated_at": now,
        "updated_at": now,
    }

    if summary.get("is_minted") and current_id:
        _supersede_active_records(project_id, keep_mint_record_id=current_id)
        cleanup = mark_obsolete_mint_jobs_for_project(
            project_id,
            current_mint_record_id=current_id,
            reason="canonical_mint_succeeded",
        )
        project_updates.update(
            {
                "minted_at": current.get("minted_at"),
                "mint_review_state": "minted",
                "mint_review_ready": True,
                "mint_blocked": False,
                "mint_blocking_reasons": [],
                "mint_readiness_snapshot": {
                    "current_status": "minted",
                    "mint_eligible": True,
                    "mint_review_ready": True,
                    "blocking_reasons": [],
                    "token_id": summary.get("token_id"),
                    "tx_hash": summary.get("tx_hash"),
                    "version_number": summary.get("version_number"),
                    "updated_at": now,
                },
            }
        )
    elif current_status == "failed":
        project_updates.update(
            {
                "mint_review_state": "failed",
                "mint_review_ready": False,
                "mint_blocked": True,
                "mint_blocking_reasons": [summary.get("error_code") or "current_mint_failed"],
                "mint_readiness_snapshot": {
                    "current_status": "failed",
                    "mint_eligible": False,
                    "mint_review_ready": False,
                    "blocking_reasons": [summary.get("error_code") or "current_mint_failed"],
                    "updated_at": now,
                },
            }
        )

    _projects_collection().update_one(
        {"_id": {"$in": _id_candidates(project_id)}},
        {"$set": project_updates},
    )

    return {
        "project_id": _normalize(project_id),
        "canonical_mint": resolve_canonical_mint_status(project_id, include_history=True),
        "job_cleanup": cleanup,
        "id_normalization": id_normalization,
    }


def list_pending_approvals(mint_record_id: str) -> list[str]:
    cursor = _approvals_collection().find(
        {"mint_record_id": {"$in": _id_candidates(mint_record_id)}, "status": "pending"}
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
        "project_id": {"$in": _id_candidates(project_id)},
        "mint_record_id": {"$in": _id_candidates(mint_record_id)},
        "approval_type": _normalize(approval_type),
    }
    existing = _approvals_collection().find_one(query)
    document = {
        "project_id": _object_id_or_text(project_id),
        "mint_record_id": _object_id_or_text(mint_record_id),
        "approval_type": _normalize(approval_type),
        "status": _normalize(status) or "pending",
        "approved_by_user_id": _object_id_or_text(approved_by_user_id),
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
            "mint_record_id": {"$in": _id_candidates(mint_record_id)},
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
    include_minted: bool = False,
) -> None:
    statuses = set(ACTIVE_MINT_RECORD_STATUSES)
    if include_minted:
        statuses.update(MINTED_MINT_RECORD_STATUSES)
    query: dict[str, Any] = {
        "project_id": {"$in": _id_candidates(project_id)},
        "mint_status": {"$in": list(statuses)},
    }
    keep_candidates = _id_candidates(keep_mint_record_id)
    if keep_candidates:
        query["_id"] = {"$nin": keep_candidates}

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
    documents = _project_record_documents(project_id)
    if not documents:
        return 1
    return max(int(document.get("version_number") or 0) for document in documents) + 1


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

    existing_summary = resolve_canonical_mint_status(project_id, include_history=False)
    existing = existing_summary.get("current_record")
    if not isinstance(existing, dict):
        existing = None
    explicit_new_version = version_strategy in REQUEUE_VERSION_STRATEGIES
    if (
        version_strategy == "new_version_if_needed"
        and existing is not None
        and (
            _canonical_record_status(existing.get("mint_status")) in {"draft", "approved", "queued", "processing", "minted"}
        )
    ):
        return existing
    if existing_summary.get("is_minted") and not explicit_new_version:
        if existing is None:
            raise ValueError("Canonical mint summary is missing the current mint record.")
        return existing

    version_number = _next_version_number(project_id)
    project_doc_id = _normalize(project.get("_id"))
    now = _now()

    document: dict[str, Any] = {
        "project_id": _object_id_or_text(project_doc_id),
        "household_id": _object_id_or_text(project.get("household_id")),
        "family_id": _object_id_or_text(project.get("family_id")),
        "user_id": _object_id_or_text(project.get("owner_user_id")),
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
    _supersede_active_records(
        project_doc_id,
        keep_mint_record_id=mint_record_id,
        include_minted=explicit_new_version,
    )
    if explicit_new_version:
        mark_obsolete_mint_jobs_for_project(
            project_doc_id,
            current_mint_record_id=mint_record_id,
            reason="explicit_new_mint_version_created",
        )

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
    normalized_wallet = _normalize_wallet_address(wallet_address, required=True)

    next_poster_style = record["poster_style"]
    if next_poster_style == "approved_poster" and not approved_poster_opt_in:
        next_poster_style = "abstract_cover"

    _records_collection().update_one(
        {"_id": _to_object_id(mint_record_id)},
        {
            "$set": {
                "customer_wallet": normalized_wallet,
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
            "wallet_address": normalized_wallet,
        },
    )
    return _recompute_mint_approval_state(mint_record_id)


def mark_mint_queued(mint_record_id: str) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")
    if record["mint_status"] not in {"approved", "queued"}:
        raise ValueError("Mint record must be approved before queueing.")
    canonical = resolve_canonical_mint_status(record["project_id"], include_history=False)
    if canonical.get("is_minted"):
        mark_obsolete_mint_jobs_for_project(
            record["project_id"],
            current_mint_record_id=_normalize(canonical.get("current_mint_record_id")),
            reason="canonical_mint_already_minted",
        )
        raise ValueError("Project already has a canonical minted record.")
    if canonical.get("current_mint_record_id") and canonical["current_mint_record_id"] != mint_record_id:
        raise ValueError("Only the current canonical mint record may be queued.")

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
                "mint_status": "processing",
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
    refreshed = get_mint_record(mint_record_id)
    if refreshed is not None:
        mark_obsolete_mint_jobs_for_project(
            refreshed["project_id"],
            current_mint_record_id=mint_record_id,
            reason="canonical_mint_succeeded",
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
    mint_policy = get_package_mint_policy(package_code)
    canonical = resolve_canonical_mint_status(project_id, include_history=True)

    return {
        "project_id": _normalize(project_id),
        "mint_enabled": bool(mint_policy.get("product_includes_onchain_anchor")),
        "current_status": canonical["current_status"],
        "canonical_status": canonical["canonical_status"],
        "current_mint_record_id": canonical["current_mint_record_id"],
        "token_id": canonical["token_id"],
        "tx_hash": canonical["tx_hash"],
        "chain": canonical["chain"],
        "contract_address": canonical["contract_address"],
        "version_number": canonical["version_number"],
        "wallet": canonical["wallet"],
        "error_code": canonical["error_code"],
        "error_message": canonical["error_message"],
        "latest": canonical["latest"],
        "current": canonical["current_record"],
        "history": canonical["history"],
        "historical_attempt_count": canonical["historical_attempt_count"],
    }
