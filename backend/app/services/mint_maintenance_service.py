from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from pymongo.collection import Collection

from app.database import get_database
from app.services.mint_job_service import sync_receipt_for_mint_record
from app.services.mint_record_service import (
    ACTIVE_MINT_RECORD_STATUSES,
    _normalize_tx_hash,
    get_mint_record,
    rebuild_mint_summary_for_project,
    resolve_canonical_mint_status,
)
from app.services.public_manifest_service import build_public_manifest


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _records_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["mint_records"])


def _iter_project_records(limit: int) -> list[dict[str, Any]]:
    cursor = _records_collection().find({}).sort(
        [("project_id", 1), ("version_number", -1), ("created_at", -1)]
    )
    return list(cursor.limit(max(1, int(limit))))


def _normalize_existing_tx_hashes(limit: int) -> dict[str, int]:
    updated = 0
    inspected = 0
    cursor = _records_collection().find({"tx_hash": {"$type": "string"}}).limit(max(1, int(limit)))

    for document in cursor:
        inspected += 1
        normalized = _normalize_tx_hash(document.get("tx_hash"))
        if not normalized or normalized == _normalize(document.get("tx_hash")):
            continue
        _records_collection().update_one(
            {"_id": document["_id"]},
            {"$set": {"tx_hash": normalized, "updated_at": _now()}},
        )
        updated += 1

    return {"inspected": inspected, "updated": updated}


def _supersede_stale_active_records(limit: int) -> dict[str, int]:
    updated = 0
    inspected = 0
    active_statuses = set(ACTIVE_MINT_RECORD_STATUSES)
    project_records = _iter_project_records(limit)
    seen_current_by_project: dict[str, str] = {}

    for document in project_records:
        project_id = _normalize(document.get("project_id"))
        if not project_id:
            continue
        status_value = _normalize(document.get("mint_status")).lower()
        if status_value not in active_statuses:
            continue
        inspected += 1
        current_id = seen_current_by_project.get(project_id)
        if not current_id:
            current = resolve_canonical_mint_status(project_id, include_history=False)
            current_id = _normalize(current.get("current_mint_record_id"))
            seen_current_by_project[project_id] = current_id
        if current_id and _normalize(document.get("_id")) == current_id:
            continue
        _records_collection().update_one(
            {"_id": document["_id"]},
            {"$set": {"mint_status": "superseded", "updated_at": _now()}},
        )
        updated += 1

    return {"inspected": inspected, "updated": updated}


def _sync_receipts(limit: int) -> dict[str, int]:
    summary = {
        "inspected": 0,
        "minted": 0,
        "pending": 0,
        "failed": 0,
        "errors": 0,
    }
    cursor = _records_collection().find(
        {
            "tx_hash": {"$type": "string", "$ne": ""},
            "mint_status": {"$nin": ["superseded", "canceled", "cancelled"]},
        }
    ).sort([("updated_at", -1)]).limit(max(1, int(limit)))

    for document in cursor:
        summary["inspected"] += 1
        mint_record_id = _normalize(document.get("_id"))
        if not mint_record_id:
            continue
        try:
            result = sync_receipt_for_mint_record(mint_record_id)
        except Exception:
            summary["errors"] += 1
            continue
        status_value = _normalize(result.get("mint_status") or result.get("status")).lower()
        if status_value == "minted":
            summary["minted"] += 1
        elif status_value == "failed":
            summary["failed"] += 1
        else:
            summary["pending"] += 1

    return summary


def _rebuild_project_mint_summaries(limit: int) -> dict[str, int]:
    summary = {"inspected": 0, "rebuilt": 0, "errors": 0}
    project_ids: list[str] = []
    for document in _records_collection().find({}, {"project_id": 1}).sort([("updated_at", -1)]).limit(max(1, int(limit))):
        project_id = _normalize(document.get("project_id"))
        if project_id and project_id not in project_ids:
            project_ids.append(project_id)

    for project_id in project_ids:
        summary["inspected"] += 1
        try:
            rebuild_mint_summary_for_project(project_id)
            summary["rebuilt"] += 1
        except Exception:
            summary["errors"] += 1
    return summary


def _republish_public_artifacts(limit: int) -> dict[str, int]:
    summary = {"inspected": 0, "republished": 0, "errors": 0}
    cursor = _records_collection().find(
        {
            "approved_at": {"$ne": None},
            "mint_status": {"$in": ["approved", "queued", "minting", "minted"]},
        }
    ).sort([("updated_at", -1)]).limit(max(1, int(limit)))

    for document in cursor:
        summary["inspected"] += 1
        mint_record_id = _normalize(document.get("_id"))
        project_id = _normalize(document.get("project_id"))
        if not mint_record_id or not project_id:
            summary["errors"] += 1
            continue
        try:
            manifest = build_public_manifest(
                project_id,
                int(document.get("version_number") or 1),
                mint_record_id=mint_record_id,
                poster_style=_normalize(document.get("poster_style")) or "abstract_cover",
                public_title_opt_in=bool(document.get("public_title_opt_in")),
                public_title=document.get("public_title"),
                public_title_kind=_normalize(document.get("public_title_kind")) or "none",
                approved_poster_opt_in=_normalize(document.get("poster_style")) == "approved_poster",
                approval_timestamp=document.get("approved_at"),
            )
            _records_collection().update_one(
                {"_id": document["_id"]},
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
            summary["republished"] += 1
        except Exception:
            summary["errors"] += 1

    return summary


def run_mint_maintenance(
    *,
    limit: int = 200,
    normalize_tx_hashes: bool = True,
    supersede_stale_records: bool = True,
    sync_receipts: bool = True,
    republish_public_artifacts: bool = True,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "limit": max(1, int(limit)),
        "normalize_tx_hashes": None,
        "supersede_stale_records": None,
        "sync_receipts": None,
        "republish_public_artifacts": None,
        "rebuild_project_mint_summaries": None,
    }

    if normalize_tx_hashes:
        summary["normalize_tx_hashes"] = _normalize_existing_tx_hashes(limit)
    if supersede_stale_records:
        summary["supersede_stale_records"] = _supersede_stale_active_records(limit)
    if sync_receipts:
        summary["sync_receipts"] = _sync_receipts(limit)
    if republish_public_artifacts:
        summary["republish_public_artifacts"] = _republish_public_artifacts(limit)
    summary["rebuild_project_mint_summaries"] = _rebuild_project_mint_summaries(limit)

    latest_records: list[dict[str, Any]] = []
    for document in _records_collection().find({}).sort([("updated_at", -1)]).limit(10):
        record = get_mint_record(_normalize(document.get("_id")))
        if record is not None:
            latest_records.append(record)

    summary["sample_latest_records"] = latest_records
    return summary
