from datetime import UTC, datetime

from app.database import get_database
from app.schemas.relationship import RelationshipCreate


def list_relationships() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.relationships.find().sort("created_at", -1))


def create_relationship(payload: RelationshipCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-relationship-preview"
        return data

    result = db.relationships.insert_one(data)
    data["_id"] = result.inserted_id
    return data
