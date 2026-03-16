from datetime import datetime, UTC

from app.database import get_database
from app.schemas.lineage_node import LineageNodeCreate


def list_lineage_nodes() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.lineage_nodes.find().sort("generation", 1))


def create_lineage_node(payload: LineageNodeCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-lineage-node-preview"
        return data

    result = db.lineage_nodes.insert_one(data)
    data["_id"] = result.inserted_id
    return data
