from datetime import datetime, UTC

from app.database import get_database
from app.schemas.intake import IntakeCreate


def list_intake_submissions() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.intake_submissions.find().sort("created_at", -1))


def create_intake_submission(payload: IntakeCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-intake-preview"
        return data

    result = db.intake_submissions.insert_one(data)
    data["_id"] = result.inserted_id
    return data
