from datetime import UTC, datetime

from app.database import get_database
from app.schemas.verification_record import VerificationRecordCreate


def list_verification_records() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.verification_records.find().sort("created_at", -1))


def create_verification_record(payload: VerificationRecordCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-verification-record-preview"
        return data

    result = db.verification_records.insert_one(data)
    data["_id"] = result.inserted_id
    return data