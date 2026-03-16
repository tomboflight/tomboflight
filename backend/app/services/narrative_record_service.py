from datetime import UTC, datetime

from app.database import get_database
from app.schemas.narrative_record import NarrativeRecordCreate


def list_narrative_records() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.narrative_records.find().sort("created_at", -1))


def create_narrative_record(payload: NarrativeRecordCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-narrative-record-preview"
        return data

    result = db.narrative_records.insert_one(data)
    data["_id"] = result.inserted_id
    return data