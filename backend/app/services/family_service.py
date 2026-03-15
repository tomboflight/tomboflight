from datetime import datetime, UTC

from app.database import get_database
from app.schemas.family import FamilyCreate


def list_families() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.families.find().sort("created_at", -1))


def create_family(payload: FamilyCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-family-preview"
        return data

    result = db.families.insert_one(data)
    data["_id"] = result.inserted_id
    return data
