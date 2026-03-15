from datetime import UTC, datetime

from bson import ObjectId

from app.database import get_database
from app.schemas.link_request import LinkRequestCreate


def list_link_requests() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.link_requests.find().sort("created_at", -1))


def create_link_request(payload: LinkRequestCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-link-request-preview"
        return data

    result = db.link_requests.insert_one(data)
    data["_id"] = result.inserted_id
    return data


def get_link_request_by_id(request_id: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        return db.link_requests.find_one({"_id": ObjectId(request_id)})
    except Exception:
        return None


def approve_link_request(request_id: str, approved_by: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(request_id)
    except Exception:
        return None

    request = db.link_requests.find_one({"_id": object_id})
    if request is None:
        return None

    db.link_requests.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "approved",
                "approved_by": approved_by,
                "approved_at": datetime.now(UTC).isoformat(),
            }
        },
    )

    existing_link = db.household_links.find_one(
        {
            "source_household_id": request["source_household_id"],
            "target_household_id": request["target_household_id"],
        }
    )

    if existing_link is None:
        household_link = {
            "source_household_id": request["source_household_id"],
            "target_household_id": request["target_household_id"],
            "relationship_type": "linked_household",
            "link_status": "approved",
            "linked_by_key": request["source_key"],
            "created_at": datetime.now(UTC).isoformat(),
        }
        db.household_links.insert_one(household_link)

    return db.link_requests.find_one({"_id": object_id})


def reject_link_request(request_id: str, rejected_by: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(request_id)
    except Exception:
        return None

    request = db.link_requests.find_one({"_id": object_id})
    if request is None:
        return None

    db.link_requests.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "rejected",
                "rejected_by": rejected_by,
                "rejected_at": datetime.now(UTC).isoformat(),
            }
        },
    )

    return db.link_requests.find_one({"_id": object_id})