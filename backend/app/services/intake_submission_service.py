from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.database import get_database

COLLECTION_NAME = "intake_submissions"


def _require_db():
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db


def serialize_intake_submission(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record["_id"]),
        "user_id": str(record["user_id"]),
        "email": record.get("email", ""),
        "package_slug": record.get("package_slug", ""),
        "package_name": record.get("package_name", ""),
        "status": record.get("status", "submitted"),
        "household": record.get("household", {}),
        "family_map": record.get("family_map", {}),
        "review": record.get("review", {}),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def create_intake_submission(*, current_user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    db = _require_db()
    now = datetime.now(UTC)

    user_id = current_user.get("_id")
    if user_id is None:
        raise RuntimeError("Current user is missing _id.")

    document = {
        "user_id": str(user_id),
        "email": current_user.get("email", ""),
        "package_slug": payload.get("package_slug", ""),
        "package_name": payload.get("package_name", ""),
        "status": "submitted",
        "household": payload.get("household", {}),
        "family_map": payload.get("family_map", {}),
        "review": payload.get("review", {}),
        "created_at": now,
        "updated_at": now,
    }

    result = db[COLLECTION_NAME].insert_one(document)
    created = db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    if created is None:
        raise RuntimeError("Failed to create intake submission.")
    return serialize_intake_submission(created)


def get_latest_intake_submission_for_user(user_id: str) -> dict[str, Any] | None:
    db = _require_db()

    record = db[COLLECTION_NAME].find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    if record is None:
        return None
    return serialize_intake_submission(record)


def list_intake_submissions_for_user(user_id: str, limit: int = 25) -> list[dict[str, Any]]:
    db = _require_db()

    cursor = (
        db[COLLECTION_NAME]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(max(1, min(limit, 100)))
    )

    return [serialize_intake_submission(doc) for doc in cursor]


def get_intake_submission_by_id_for_user(*, submission_id: str, user_id: str) -> dict[str, Any] | None:
    db = _require_db()

    if not ObjectId.is_valid(submission_id):
        return None

    record = db[COLLECTION_NAME].find_one(
        {"_id": ObjectId(submission_id), "user_id": user_id}
    )
    if record is None:
        return None
    return serialize_intake_submission(record)