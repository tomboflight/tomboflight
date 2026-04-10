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



def update_user_profile(user_id: str, *, full_name: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    normalized_name = str(full_name or '').strip()
    if not normalized_name:
        raise ValueError('full_name is required.')

    try:
        from bson import ObjectId

        object_id = ObjectId(user_id)
    except Exception:
        return None

    db.users.update_one(
        {'_id': object_id},
        {
            '$set': {
                'full_name': normalized_name,
                'updated_at': datetime.now(UTC).isoformat(),
            }
        },
    )
    return db.users.find_one({'_id': object_id})
