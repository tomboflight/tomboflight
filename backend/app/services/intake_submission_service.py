from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.database import get_database


COLLECTION_NAME = "intake_submissions"


def serialize_intake_submission(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record["_id"]),
        "user_id": str(record["user_id"]),
        "email": record["email"],
        "package_slug": record["package_slug"],
        "package_name": record["package_name"],
        "status": record["status"],
        "household": record["household"],
        "family_map": record["family_map"],
        "review": record["review"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def create_intake_submission(
    *,
    current_user: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    now = datetime.now(UTC)

    document = {
        "user_id": str(current_user["_id"]),
        "email": current_user["email"],
        "package_slug": payload["package_slug"],
        "package_name": payload["package_name"],
        "status": "submitted",
        "household": payload["household"],
        "family_map": payload["family_map"],
        "review": payload["review"],
        "created_at": now,
        "updated_at": now,
    }

    result = db[COLLECTION_NAME].insert_one(document)
    created = db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    if created is None:
        raise RuntimeError("Failed to create intake submission.")

    return serialize_intake_submission(created)


def get_latest_intake_submission_for_user(user_id: str) -> dict[str, Any] | None:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    record = db[COLLECTION_NAME].find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )

    if record is None:
        return None

    return serialize_intake_submission(record)


def get_intake_submission_by_id_for_user(
    *,
    submission_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    if not ObjectId.is_valid(submission_id):
        return None

    record = db[COLLECTION_NAME].find_one(
        {
            "_id": ObjectId(submission_id),
            "user_id": user_id,
        }
    )

    if record is None:
        return None

    return serialize_intake_submission(record)