from __future__ import annotations

import logging
from uuid import uuid4
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.core.admin_permission_registry import is_canonical_ceo_email
from app.database import get_database
from app.services.blockchain_mint_service import (
    mint_anchor,
    rebroadcast_signed_transaction,
    sync_mint_receipt,
)
from app.services.mint_record_service import (
    ACTIVE_MINT_JOB_STATUSES,
    _object_id_or_text,
    get_mint_record,
    mark_obsolete_mint_jobs_for_project,
    mark_mint_failed,
    mark_mint_minted,
    mark_mint_minting,
    mark_mint_queued,
    resolve_canonical_mint_status,
)
from app.services.poster_asset_service import build_poster_asset
from app.services.public_manifest_service import (
    build_public_manifest,
    get_public_manifest_for_mint_record,
)

JOB_SEQUENCE = (
    "prepare_manifest",
    "generate_poster",
    "mint_anchor",
    "sync_receipt",
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_tx_hash(value: Any) -> str:
    normalized = _normalize(value)
    if not normalized:
        return ""
    if not normalized.lower().startswith("0x"):
        normalized = f"0x{normalized}"
    return normalized.lower()


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


def _collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_jobs"])


def _records_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_records"])


def _mint_runtime_locks_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_runtime_locks"])


def _clear_completed_signed_transaction(mint_record_id: str) -> None:
    record_id = _to_object_id(mint_record_id)
    if record_id is None:
        return
    _records_collection().update_one(
        {"_id": record_id},
        {
            "$set": {
                "signed_transaction": None,
                "broadcast_state": "confirmed",
                "transaction_confirmed_at": _now(),
                "updated_at": _now(),
            }
        },
    )


def _acquire_signer_lease(mint_record_id: str) -> str:
    now = _now()
    lease_token = f"{mint_record_id}:{uuid4().hex}"
    try:
        document = _mint_runtime_locks_collection().find_one_and_update(
            {
                "_id": "evm_mint_signer",
                "$or": [
                    {"expires_at": {"$lte": now}},
                    {"lease_token": lease_token},
                ],
            },
            {
                "$set": {
                    "lease_token": lease_token,
                    "mint_record_id": mint_record_id,
                    "locked_at": now,
                    "expires_at": now + timedelta(minutes=4),
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError as exc:
        raise RuntimeError(
            "Another mint transaction currently owns the blockchain signer lease."
        ) from exc
    if document is None or _normalize(document.get("lease_token")) != lease_token:
        raise RuntimeError(
            "Another mint transaction currently owns the blockchain signer lease."
        )
    return lease_token


def _release_signer_lease(lease_token: str) -> None:
    now = _now()
    _mint_runtime_locks_collection().update_one(
        {"_id": "evm_mint_signer", "lease_token": lease_token},
        {
            "$set": {
                "lease_token": None,
                "mint_record_id": None,
                "released_at": now,
                "expires_at": now,
            }
        },
    )


def ensure_mint_job_indexes() -> None:
    collection = _collection()
    existing = collection.index_information()
    definitions = [
        (
            [("status", 1), ("run_after", 1), ("priority", -1)],
            "status_1_run_after_1_priority_-1",
        ),
        ([("project_id", 1), ("created_at", -1)], "project_id_1_created_at_-1"),
        ([("mint_record_id", 1)], "mint_record_id_1"),
    ]

    for keys, name in definitions:
        if name in existing:
            continue
        try:
            collection.create_index(keys, name=name)
        except OperationFailure:
            continue
    # This sparse idempotency key closes the check-then-insert race without
    # invalidating historical rows created before job keys existed.
    collection.create_index(
        [("job_key", 1)],
        name="job_key_1_unique",
        unique=True,
        sparse=True,
    )


def _serialize_job(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize(document.get("_id")),
        "project_id": _normalize(document.get("project_id")),
        "mint_record_id": _normalize(document.get("mint_record_id")),
        "job_type": _normalize(document.get("job_type")),
        "status": _normalize(document.get("status")) or "queued",
        "attempt_count": int(document.get("attempt_count") or 0),
        "max_attempts": int(document.get("max_attempts") or 5),
        "priority": int(document.get("priority") or 50),
        "run_after": document.get("run_after") or _now(),
        "locked_by": _normalize(document.get("locked_by")) or None,
        "locked_at": document.get("locked_at"),
        "started_at": document.get("started_at"),
        "finished_at": document.get("finished_at"),
        "payload": document.get("payload") or {},
        "result": document.get("result") or {},
        "error_code": _normalize(document.get("error_code")) or None,
        "error_message": _normalize(document.get("error_message")) or None,
        "created_at": document.get("created_at") or _now(),
        "updated_at": document.get("updated_at") or _now(),
    }


def enqueue_job(
    *,
    project_id: str,
    mint_record_id: str,
    job_type: str,
    priority: int = 50,
    run_after: datetime | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_job_type = _normalize(job_type)
    if normalized_job_type not in JOB_SEQUENCE:
        raise ValueError("Unsupported mint job type.")

    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")
    if record["project_id"] != _normalize(project_id):
        raise ValueError("Mint record does not belong to the requested project.")

    canonical = resolve_canonical_mint_status(project_id, include_history=False)
    canonical_record_id = _normalize(canonical.get("current_mint_record_id"))
    if canonical.get("is_minted"):
        mark_obsolete_mint_jobs_for_project(
            project_id,
            current_mint_record_id=canonical_record_id,
            reason="canonical_mint_already_minted",
        )
        if canonical_record_id == _normalize(mint_record_id) and normalized_job_type == "sync_receipt":
            pass
        else:
            raise ValueError("Project already has a canonical minted record.")
    elif canonical_record_id and canonical_record_id != _normalize(mint_record_id):
        raise ValueError("Mint job belongs to a non-canonical mint record.")

    now = _now()
    job_key = (
        f"{_normalize(project_id)}:{_normalize(mint_record_id)}:{normalized_job_type}"
    )
    document = {
        "project_id": _object_id_or_text(project_id),
        "mint_record_id": _object_id_or_text(mint_record_id),
        "job_type": normalized_job_type,
        "job_key": job_key,
        "status": "queued",
        "attempt_count": 0,
        "max_attempts": 5,
        "priority": priority,
        "run_after": run_after or now,
        "locked_by": None,
        "locked_at": None,
        "started_at": None,
        "finished_at": None,
        "payload": payload or {},
        "result": {},
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }

    existing = _collection().find_one(
        {
            "project_id": {"$in": _id_candidates(document["project_id"])},
            "mint_record_id": {"$in": _id_candidates(document["mint_record_id"])},
            "job_type": document["job_type"],
            "status": {"$in": list(ACTIVE_MINT_JOB_STATUSES)},
        }
    )
    if existing is not None:
        return _serialize_job(existing)

    terminal_existing = _collection().find_one({"job_key": job_key})
    if terminal_existing is not None:
        terminal_status = _normalize(terminal_existing.get("status")).lower()
        attempts = int(terminal_existing.get("attempt_count") or 0)
        max_attempts = int(terminal_existing.get("max_attempts") or 5)
        if (
            terminal_status in {"failed", "succeeded", "canceled"}
            and attempts < max_attempts
            and normalized_job_type == "sync_receipt"
        ):
            _collection().update_one(
                {"_id": terminal_existing["_id"]},
                {
                    "$set": {
                        "status": "queued",
                        "run_after": run_after or now,
                        "locked_by": None,
                        "locked_at": None,
                        "started_at": None,
                        "finished_at": None,
                        "error_code": None,
                        "error_message": None,
                        "updated_at": now,
                    }
                },
            )
            refreshed = _collection().find_one({"_id": terminal_existing["_id"]})
            return _serialize_job(refreshed or terminal_existing)
        return _serialize_job(terminal_existing)

    try:
        result = _collection().insert_one(document)
    except DuplicateKeyError:
        raced = _collection().find_one({"job_key": job_key})
        if raced is None:
            raise
        return _serialize_job(raced)
    saved = _collection().find_one({"_id": result.inserted_id}) or document
    return _serialize_job(saved)


def queue_mint_pipeline(
    project_id: str,
    mint_record_id: str,
    *,
    queued_by: str = "system",
) -> list[dict[str, Any]]:
    normalized_queued_by = _normalize(queued_by).lower()
    if not is_canonical_ceo_email(normalized_queued_by):
        raise ValueError(
            "Only the CEO master account can queue an approved NFT."
        )
    now = _now()

    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")
    if record["project_id"] != _normalize(project_id):
        raise ValueError("Mint record does not belong to the requested project.")
    canonical = resolve_canonical_mint_status(project_id, include_history=False)
    if canonical.get("is_minted"):
        mark_obsolete_mint_jobs_for_project(
            project_id,
            current_mint_record_id=_normalize(canonical.get("current_mint_record_id")),
            reason="canonical_mint_already_minted",
        )
        raise ValueError("Project already has a canonical minted record.")
    if canonical.get("current_mint_record_id") and canonical["current_mint_record_id"] != _normalize(mint_record_id):
        raise ValueError("Only the current canonical mint record can be queued.")

    mark_mint_queued(mint_record_id)

    return [
        enqueue_job(
            project_id=project_id,
            mint_record_id=mint_record_id,
            job_type="prepare_manifest",
            priority=90,
            payload={"version_number": record["version_number"]},
        ),
        enqueue_job(
            project_id=project_id,
            mint_record_id=mint_record_id,
            job_type="generate_poster",
            priority=80,
            payload={"version_number": record["version_number"]},
        ),
        enqueue_job(
            project_id=project_id,
            mint_record_id=mint_record_id,
            job_type="mint_anchor",
            priority=70,
            payload={"version_number": record["version_number"]},
        ),
        enqueue_job(
            project_id=project_id,
            mint_record_id=mint_record_id,
            job_type="sync_receipt",
            priority=60,
            run_after=now + timedelta(seconds=45),
            payload={"version_number": record["version_number"]},
        ),
    ]


def _execute_prepare_manifest(job: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    manifest = build_public_manifest(
        record["project_id"],
        record["version_number"],
        mint_record_id=record["id"],
        poster_style=record["poster_style"],
        public_title_opt_in=bool(record["public_title_opt_in"]),
        public_title=record.get("public_title"),
        public_title_kind=record.get("public_title_kind") or "none",
        approved_poster_opt_in=record["poster_style"] == "approved_poster",
        approval_timestamp=record.get("approved_at"),
    )

    _records_collection().update_one(
        {"_id": _to_object_id(record["id"])},
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

    return {
        "metadata_uri": manifest["metadata_uri"],
        "poster_image_uri_public": manifest["poster_image_uri_public"],
    }


def _execute_generate_poster(job: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    manifest = get_public_manifest_for_mint_record(record["id"])
    public_token_id = _normalize((manifest or {}).get("public_token_id"))
    if not public_token_id:
        public_token_id = f"TOL-{_now().year}-{record['project_id'][-6:].upper()}-V{record['version_number']:02d}"

    poster_asset = build_poster_asset(
        project_id=record["project_id"],
        version_number=record["version_number"],
        public_token_id=public_token_id,
        requested_style=record["poster_style"],
        approved_poster_opt_in=record["poster_style"] == "approved_poster",
    )

    _records_collection().update_one(
        {"_id": _to_object_id(record["id"])},
        {
            "$set": {
                "poster_style": poster_asset["poster_style"],
                "poster_image_uri_public": poster_asset["poster_image_uri_public"],
                "updated_at": _now(),
            }
        },
    )

    return poster_asset


def _execute_mint_anchor(job: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    del job

    manifest = get_public_manifest_for_mint_record(record["id"])
    if manifest is None:
        raise RuntimeError("Public manifest is missing for this mint record.")

    lease_token = _acquire_signer_lease(record["id"])
    try:
        raw_record = _records_collection().find_one(
            {"_id": _to_object_id(record["id"])}
        ) or {}
        existing_tx_hash = _normalize_tx_hash(
            raw_record.get("tx_hash") or record.get("tx_hash")
        )
        if existing_tx_hash:
            if (
                _normalize(raw_record.get("broadcast_state")).lower() == "prepared"
                and _normalize(raw_record.get("signed_transaction"))
            ):
                rebroadcast_signed_transaction(
                    _normalize(raw_record.get("signed_transaction"))
                )
                _records_collection().update_one(
                    {"_id": _to_object_id(record["id"])},
                    {
                        "$set": {
                            "broadcast_state": "submitted",
                            "broadcast_recovered_at": _now(),
                            "updated_at": _now(),
                        }
                    },
                )
            return sync_receipt_for_mint_record(record["id"])

        def persist_prepared_transaction(payload: dict[str, Any]) -> None:
            tx_hash = _normalize_tx_hash(payload.get("tx_hash"))
            _records_collection().update_one(
                {"_id": _to_object_id(record["id"])},
                {
                    "$set": {
                        "tx_hash": tx_hash,
                        "mint_nonce": payload.get("nonce"),
                        "signed_transaction": payload.get("signed_transaction"),
                        "broadcast_state": "prepared",
                        "transaction_prepared_at": _now(),
                        "updated_at": _now(),
                    }
                },
            )
            mark_mint_minting(record["id"], tx_hash=tx_hash)

        def persist_broadcast(payload: dict[str, Any]) -> None:
            _records_collection().update_one(
                {"_id": _to_object_id(record["id"])},
                {
                    "$set": {
                        "broadcast_state": "submitted",
                        "transaction_broadcast_at": _now(),
                        "updated_at": _now(),
                    }
                },
            )

        mark_mint_minting(record["id"])
        mint_result = mint_anchor(
            metadata_uri=manifest["metadata_uri"],
            recipient_wallet=record.get("customer_wallet"),
            token_type=record.get("token_type") or "portrait_anchor",
            on_transaction_prepared=persist_prepared_transaction,
            on_transaction_broadcast=persist_broadcast,
        )
    finally:
        _release_signer_lease(lease_token)

    token_id = _normalize(mint_result.get("token_id"))
    tx_hash = _normalize_tx_hash(mint_result.get("tx_hash"))
    if tx_hash:
        mark_mint_minting(record["id"], tx_hash=tx_hash)
    if token_id and tx_hash:
        mark_mint_minted(
            record["id"],
            token_id=token_id,
            tx_hash=tx_hash,
            minted_by="system",
            contract_address=mint_result.get("contract_address"),
            chain=mint_result.get("chain"),
        )
        _clear_completed_signed_transaction(record["id"])

    return mint_result


def _job_dependencies(job_type: str) -> tuple[str, ...]:
    try:
        index = JOB_SEQUENCE.index(job_type)
    except ValueError:
        return tuple()
    return JOB_SEQUENCE[:index]


def _queued_or_running_dependency(project_id: str, mint_record_id: str, job_type: str) -> dict[str, Any] | None:
    for dependency in _job_dependencies(job_type):
        pending_job = _collection().find_one(
            {
                "project_id": {"$in": _id_candidates(project_id)},
                "mint_record_id": {"$in": _id_candidates(mint_record_id)},
                "job_type": dependency,
                "status": {"$in": list(ACTIVE_MINT_JOB_STATUSES)},
            }
        )
        if pending_job is not None:
            return pending_job
        failed_job = _collection().find_one(
            {
                "project_id": {"$in": _id_candidates(project_id)},
                "mint_record_id": {"$in": _id_candidates(mint_record_id)},
                "job_type": dependency,
                "status": "failed",
            }
        )
        if failed_job is not None:
            return failed_job
    return None


def sync_receipt_for_mint_record(mint_record_id: str) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")
    canonical = resolve_canonical_mint_status(record["project_id"], include_history=False)
    if canonical.get("current_mint_record_id") and canonical["current_mint_record_id"] != record["id"]:
        return {
            "mint_record_id": mint_record_id,
            "status": "obsolete",
            "message": "Receipt sync skipped because this mint record is historical.",
            "canonical_mint": canonical,
        }
    tx_hash = _normalize_tx_hash(record.get("tx_hash"))
    if not tx_hash:
        return {
            "mint_record_id": mint_record_id,
            "status": "pending",
            "message": "Mint transaction hash is not available yet.",
        }

    receipt = sync_mint_receipt(tx_hash)
    synced_status = _normalize(receipt.get("status")).lower()
    token_id = _normalize(receipt.get("token_id")) or _normalize(record.get("token_id"))
    synced_tx_hash = _normalize_tx_hash(receipt.get("tx_hash")) or tx_hash

    if synced_status == "failed":
        return mark_mint_failed(
            mint_record_id,
            error_code="mint_receipt_failed",
            error_message="Mint transaction failed on-chain.",
        )

    if token_id and synced_status in {"minted", "confirmed"}:
        minted = mark_mint_minted(
            mint_record_id,
            token_id=token_id,
            tx_hash=synced_tx_hash,
            minted_by="system",
            contract_address=receipt.get("contract_address"),
            chain=receipt.get("chain"),
        )
        _clear_completed_signed_transaction(mint_record_id)
        return minted

    if synced_status == "confirmed":
        return mark_mint_failed(
            mint_record_id,
            error_code="mint_token_id_missing",
            error_message=(
                "Mint receipt was confirmed on-chain but no ERC721 Transfer token id "
                "could be extracted from the receipt."
            ),
        )

    return {
        "mint_record_id": mint_record_id,
        "tx_hash": synced_tx_hash,
        "status": synced_status or "pending",
    }


def _finish_job(
    job_id: ObjectId,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    _collection().update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": status,
                "result": result or {},
                "error_code": _normalize(error_code) or None,
                "error_message": _normalize(error_message) or None,
                "finished_at": _now(),
                "updated_at": _now(),
            }
        },
    )
    saved = _collection().find_one({"_id": job_id})
    return _serialize_job(saved or {"_id": job_id})


def run_next_job(worker_id: str) -> dict[str, Any]:
    now = _now()
    stale_before = now - timedelta(minutes=5)
    collection = _collection()
    if hasattr(collection, "update_many"):
        collection.update_many(
            {
                "status": "started",
                "locked_at": {"$lte": stale_before},
            },
            {
                "$set": {
                    "status": "queued",
                    "locked_by": None,
                    "locked_at": None,
                    "started_at": None,
                    "run_after": now,
                    "error_code": "stale_worker_lease_recovered",
                    "error_message": "A stale worker lease was recovered automatically.",
                    "updated_at": now,
                }
            },
        )
    job = collection.find_one_and_update(
        {
            "status": "queued",
            "run_after": {"$lte": now},
        },
        {
            "$set": {
                "status": "started",
                "locked_by": _normalize(worker_id) or "api-worker",
                "locked_at": now,
                "started_at": now,
                "updated_at": now,
            },
            "$inc": {"attempt_count": 1},
        },
        sort=[("priority", -1), ("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )

    if job is None:
        return {
            "status": "idle",
            "message": "No mint jobs are queued.",
        }

    serialized_job = _serialize_job(job)
    record = get_mint_record(serialized_job["mint_record_id"])
    if record is None:
        return _finish_job(
            job["_id"],
            status="failed",
            error_code="mint_record_missing",
            error_message="Mint record was not found.",
        )

    canonical = resolve_canonical_mint_status(record["project_id"], include_history=False)
    canonical_record_id = _normalize(canonical.get("current_mint_record_id"))
    if canonical.get("is_minted") and canonical_record_id == record["id"] and serialized_job["job_type"] != "sync_receipt":
        return _finish_job(
            job["_id"],
            status="obsolete",
            error_code="mint_already_completed",
            error_message="Canonical mint record is already minted.",
        )
    if canonical.get("current_status") == "failed":
        return _finish_job(
            job["_id"],
            status="canceled",
            error_code="mint_record_failed",
            error_message="Canonical mint record is failed and must be repaired before jobs can run.",
        )
    if canonical_record_id and canonical_record_id != record["id"]:
        return _finish_job(
            job["_id"],
            status="obsolete",
            error_code="mint_record_superseded",
            error_message="Mint job belongs to a historical mint record.",
        )
    if _normalize(record.get("canonical_mint_status")).lower() in {"superseded", "canceled"}:
        return _finish_job(
            job["_id"],
            status="obsolete",
            error_code="mint_record_not_current",
            error_message="Mint record is historical and cannot run jobs.",
        )

    dependency = _queued_or_running_dependency(
        serialized_job["project_id"],
        serialized_job["mint_record_id"],
        serialized_job["job_type"],
    )
    if dependency is not None:
        dependency_status = _normalize(dependency.get("status")).lower()
        if dependency_status == "failed":
            return _finish_job(
                job["_id"],
                status="canceled",
                error_code="mint_dependency_failed",
                error_message=(
                    "A required earlier mint job failed, so this job was cancelled."
                ),
            )

        _collection().update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "status": "queued",
                    "locked_by": None,
                    "locked_at": None,
                    "started_at": None,
                    "run_after": now + timedelta(seconds=30),
                    "updated_at": _now(),
                }
            },
        )
        return _serialize_job(_collection().find_one({"_id": job["_id"]}) or job)

    logger.info(
        "Running Tomb of Light mint job",
        extra={
            "project_id": record["project_id"],
            "mint_record_id": record["id"],
            "job_type": serialized_job["job_type"],
            "version_number": record["version_number"],
            "contract_address": record.get("contract_address"),
            "recipient_wallet": record.get("customer_wallet"),
            "tx_hash": record.get("tx_hash"),
        },
    )

    try:
        if serialized_job["job_type"] == "prepare_manifest":
            result = _execute_prepare_manifest(serialized_job, record)
        elif serialized_job["job_type"] == "generate_poster":
            result = _execute_generate_poster(serialized_job, record)
        elif serialized_job["job_type"] == "mint_anchor":
            result = _execute_mint_anchor(serialized_job, record)
        elif serialized_job["job_type"] == "sync_receipt":
            result = sync_receipt_for_mint_record(record["id"])
        else:
            raise RuntimeError("Unsupported mint job type.")

        if (
            serialized_job["job_type"] == "sync_receipt"
            and _normalize((result or {}).get("status")).lower() == "pending"
        ):
            _collection().update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "status": "queued",
                        "run_after": _now() + timedelta(seconds=60),
                        "locked_by": None,
                        "locked_at": None,
                        "started_at": None,
                        "finished_at": None,
                        "result": result or {},
                        "updated_at": _now(),
                    }
                },
            )
            refreshed = _collection().find_one({"_id": job["_id"]}) or job
            return _serialize_job(refreshed)

        return _finish_job(
            job["_id"],
            status="succeeded",
            result=result,
        )
    except Exception as exc:
        logger.exception(
            "Tomb of Light mint job failed",
            extra={
                "project_id": record["project_id"],
                "mint_record_id": record["id"],
                "job_type": serialized_job["job_type"],
                "version_number": record["version_number"],
                "contract_address": record.get("contract_address"),
                "recipient_wallet": record.get("customer_wallet"),
                "tx_hash": record.get("tx_hash"),
            },
        )
        retry_delay = now + timedelta(minutes=5)
        attempt_count = int(serialized_job.get("attempt_count") or 0)
        max_attempts = int(serialized_job.get("max_attempts") or 5)
        will_retry = attempt_count < max_attempts
        if not will_retry:
            mark_mint_failed(
                record["id"],
                error_code="mint_job_failed",
                error_message=str(exc),
            )
        _collection().update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "status": "queued" if will_retry else "failed",
                    "run_after": retry_delay,
                    "locked_by": None,
                    "locked_at": None,
                    "started_at": None if will_retry else serialized_job.get("started_at"),
                    "error_code": "mint_job_failed",
                    "error_message": str(exc),
                    "finished_at": None if will_retry else _now(),
                    "updated_at": _now(),
                }
            },
        )
        saved = _collection().find_one({"_id": job["_id"]}) or job
        return _serialize_job(saved)
