from datetime import datetime, UTC

from app.database import get_database
from app.schemas.user import UserCreate


def list_users() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.users.find().sort("created_at", -1))


def create_user(payload: UserCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()
    data["full_name"] = f"{payload.first_name} {payload.last_name}".strip()
    data["status"] = data.get("status") or "active"
    data["last_login_at"] = None
    data["password_reset_requested_at"] = None
    data["password_reset_expires_at"] = None
    data["password_reset_token_hash"] = None
    data["password_reset_requested_via"] = None
    data["password_reset_requested_by"] = None
    data["password_reset_requested_by_user_id"] = None
    data["password_reset_used_at"] = None

    if db is None:
        data["_id"] = "local-user-preview"
        return data

    result = db.users.insert_one(data)
    data["_id"] = result.inserted_id
    return data
