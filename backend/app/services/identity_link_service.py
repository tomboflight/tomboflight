from datetime import UTC, datetime

from app.database import get_database
from app.schemas.identity_link import IdentityLinkCreate


def list_identity_links() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.identity_links.find().sort("created_at", -1))


def create_identity_link(payload: IdentityLinkCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-identity-link-preview"
        return data

    result = db.identity_links.insert_one(data)
    data["_id"] = result.inserted_id
    return data