from datetime import UTC, datetime

from app.database import get_database
from app.schemas.family_network import FamilyNetworkCreate
from app.utils.keygen import generate_key


def list_family_networks() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.family_networks.find().sort("created_at", -1))


def create_family_network(payload: FamilyNetworkCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()
    data["network_key"] = generate_key("NET")

    if db is None:
        data["_id"] = "local-network-preview"
        return data

    while db.family_networks.find_one({"network_key": data["network_key"]}) is not None:
        data["network_key"] = generate_key("NET")

    result = db.family_networks.insert_one(data)
    data["_id"] = result.inserted_id
    return data