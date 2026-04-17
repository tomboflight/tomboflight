from datetime import UTC, datetime

from app.database import get_database
from app.schemas.verification_record import (
    VerificationRecordCreate,
    build_verification_record_document,
    normalize_verification_record_data,
)


def list_verification_records() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.verification_records.find().sort("created_at", -1))


def create_verification_record(payload: VerificationRecordCreate) -> dict:
    db = get_database()
    now_iso = datetime.now(UTC).isoformat()
    data = build_verification_record_document(
        payload.model_dump(),
        now_iso=now_iso,
    )

    if db is None:
        data["_id"] = "local-verification-record-preview"
        return data

    result = db.verification_records.insert_one(data)
    data["_id"] = result.inserted_id
    return data


def backfill_verification_record_schema(limit: int = 1000) -> dict[str, int]:
    db = get_database()
    if db is None:
        return {"matched": 0, "updated": 0}

    cursor = db.verification_records.find(
        {
            "$or": [
                {"verification_type": {"$exists": False}},
                {"verification_status": {"$exists": False}},
                {"reviewed_by": {"$exists": False}},
                {"record_type": {"$exists": False}},
                {"status": {"$exists": False}},
            ]
        }
    ).limit(max(1, min(limit, 10000)))

    matched = 0
    updated = 0
    now_iso = datetime.now(UTC).isoformat()

    for record in cursor:
        matched += 1
        normalized = build_verification_record_document(record, now_iso=now_iso)
        normalized.pop("_id", None)
        result = db.verification_records.update_one(
            {"_id": record["_id"]},
            {"$set": normalized},
        )
        updated += int(getattr(result, "modified_count", 0) or 0)

    return {"matched": matched, "updated": updated}


def normalized_verification_record_snapshot(record: dict) -> dict:
    return normalize_verification_record_data(record)
