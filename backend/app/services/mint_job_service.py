from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from app.database import get_database
from app.services.blockchain_mint_service import mint_anchor, sync_mint_receipt
from app.services.mint_record_service import (
    get_mint_record,
    get_latest_mint_record,
    mark_mint_failed,
    mark_mint_minted,
    mark_mint_minting,
    mark_mint_queued,
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


def _collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_jobs"])


def _records_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_records"])


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
    now = _now()
    document = {
        "project_id": _normalize(project_id),
        "mint_record_id": _normalize(mint_record_id),
        "job_type": _normalize(job_type),
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
            "project_id": document["project_id"],
            "mint_record_id": document["mint_record_id"],
            "job_type": document["job_type"],
            "status": {"$in": ["queued", "running"]},
        }
    )
    if existing is not None:
        return _serialize_job(existing)

    result = _collection().insert_one(document)
    saved = _collection().find_one({"_id": result.inserted_id}) or document
    return _serialize_job(saved)


def queue_mint_pipeline(
    project_id: str,
    mint_record_id: str,
    *,
    queued_by: str = "system",
) -> list[dict[str, Any]]:
    del queued_by
    now = _now()

    record = get_mint_record(mint_record_id)
    if record is None:
        raise ValueError("Mint record not found.")
    if record["project_id"] != _normalize(project_id):
        raise ValueError("Mint record does not belong to the requested project.")

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

    mark_mint_minting(record["id"])
    mint_result = mint_anchor(
        metadata_uri=manifest["metadata_uri"],
        recipient_wallet=record.get("customer_wallet"),
        token_type=record.get("token_type") or "portrait_anchor",
    )

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
                "project_id": _normalize(project_id),
                "mint_record_id": _normalize(mint_record_id),
                "job_type": dependency,
                "status": {"$in": ["queued", "running"]},
            }
        )
        if pending_job is not None:
            return pending_job
        failed_job = _collection().find_one(
            {
                "project_id": _normalize(project_id),
                "mint_record_id": _normalize(mint_record_id),
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
        return mark_mint_minted(
            mint_record_id,
            token_id=token_id,
            tx_hash=synced_tx_hash,
            minted_by="system",
            contract_address=receipt.get("contract_address"),
            chain=receipt.get("chain"),
        )

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
    job = _collection().find_one_and_update(
        {
            "status": "queued",
            "run_after": {"$lte": now},
        },
        {
            "$set": {
                "status": "running",
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

    latest = get_latest_mint_record(record["project_id"])
    if latest is None or latest["id"] != record["id"]:
        return _finish_job(
            job["_id"],
            status="cancelled",
            error_code="mint_record_superseded",
            error_message="Mint job belongs to a non-authoritative mint record.",
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
                status="cancelled",
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
            enqueue_job(
                project_id=record["project_id"],
                mint_record_id=record["id"],
                job_type="sync_receipt",
                priority=60,
                run_after=_now() + timedelta(seconds=60),
                payload={"version_number": record["version_number"]},
            )

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
        mark_mint_failed(
            record["id"],
            error_code="mint_job_failed",
            error_message=str(exc),
        )
        retry_delay = now + timedelta(minutes=5)
        _collection().update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "status": "failed",
                    "run_after": retry_delay,
                    "error_code": "mint_job_failed",
                    "error_message": str(exc),
                    "finished_at": _now(),
                    "updated_at": _now(),
                }
            },
        )
        saved = _collection().find_one({"_id": job["_id"]}) or job
        return _serialize_job(saved)
