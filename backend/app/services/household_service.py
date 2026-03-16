from datetime import UTC, datetime

from app.database import get_database
from app.schemas.household import HouseholdCreate
from app.utils.keygen import generate_key


def list_households() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.households.find().sort("created_at", -1))


def create_household(payload: HouseholdCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()
    data["household_key"] = generate_key("HSE")

    if db is None:
        data["_id"] = "local-household-preview"
        return data

    while db.households.find_one({"household_key": data["household_key"]}) is not None:
        data["household_key"] = generate_key("HSE")

    result = db.households.insert_one(data)
    data["_id"] = result.inserted_id
    return data