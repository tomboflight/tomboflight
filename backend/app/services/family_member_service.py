from datetime import datetime, UTC

from app.database import get_database
from app.schemas.family_member import FamilyMemberCreate


def list_family_members() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.family_members.find().sort("generation", 1))


def create_family_member(payload: FamilyMemberCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-family-member-preview"
        return data

    result = db.family_members.insert_one(data)
    data["_id"] = result.inserted_id
    return data
