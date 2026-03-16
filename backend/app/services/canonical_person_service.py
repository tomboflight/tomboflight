from datetime import UTC, datetime
from bson import ObjectId

from app.database import get_database
from app.schemas.canonical_person import CanonicalPersonCreate


def list_canonical_persons() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.canonical_persons.find().sort("created_at", -1))


def get_canonical_person(canonical_person_id: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    if not ObjectId.is_valid(canonical_person_id):
        return None

    return db.canonical_persons.find_one({"_id": ObjectId(canonical_person_id)})


def get_canonical_person_members(canonical_person_id: str) -> list[dict]:
    db = get_database()
    if db is None:
        return []

    identity_links = list(
        db.identity_links.find({"canonical_person_id": canonical_person_id})
    )

    member_ids = []
    for link in identity_links:
        member_id = link.get("family_member_id")
        if member_id and ObjectId.is_valid(member_id):
            member_ids.append(ObjectId(member_id))

    if not member_ids:
        return []

    members = list(
        db.family_members.find({"_id": {"$in": member_ids}})
    )

    for member in members:
        member["_id"] = str(member["_id"])

    return members


def create_canonical_person(payload: CanonicalPersonCreate) -> dict:
    db = get_database()
    data = payload.model_dump()

    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-canonical-person-preview"
        return data

    result = db.canonical_persons.insert_one(data)
    data["_id"] = result.inserted_id

    return data