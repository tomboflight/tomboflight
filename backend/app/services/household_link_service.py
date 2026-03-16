from datetime import UTC, datetime

from app.database import get_database
from app.schemas.household_link import HouseholdLinkCreate


def list_household_links() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.household_links.find().sort("created_at", -1))


def create_household_link(payload: HouseholdLinkCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-household-link-preview"
        return data

    result = db.household_links.insert_one(data)
    data["_id"] = result.inserted_id
    return data
