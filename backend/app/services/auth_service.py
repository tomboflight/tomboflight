from datetime import UTC, datetime

from bson import ObjectId

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_database
from app.schemas.auth import UserCreate


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_user_response(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
        "created_at": user["created_at"],
        "policy_version": user.get("policy_version"),
        "terms_accepted_at": user.get("terms_accepted_at"),
        "privacy_accepted_at": user.get("privacy_accepted_at"),
        "eligibility_attested_at": user.get("eligibility_attested_at"),
    }


def register_user(payload: UserCreate) -> dict | None:
    if not payload.terms_accepted:
        raise ValueError("You must accept the Terms of Service.")
    if not payload.privacy_accepted:
        raise ValueError("You must accept the Privacy Policy.")
    if not payload.eligibility_attested:
        raise ValueError(
            "You must confirm your eligibility and authority to create the account."
        )

    db = get_database()
    now_iso = _now_iso()

    if db is None:
        return {
            "_id": "local-user-preview",
            "email": payload.email.lower(),
            "full_name": payload.full_name.strip(),
            "role": payload.role,
            "status": "active",
            "created_at": now_iso,
            "policy_version": payload.policy_version,
            "terms_accepted_at": now_iso,
            "privacy_accepted_at": now_iso,
            "eligibility_attested_at": now_iso,
        }

    existing = db.users.find_one({"email": payload.email.lower()})
    if existing is not None:
        return None

    user = {
        "email": payload.email.lower(),
        "full_name": payload.full_name.strip(),
        "role": payload.role,
        "status": "active",
        "password_hash": hash_password(payload.password),
        "created_at": now_iso,
        "policy_version": payload.policy_version,
        "terms_accepted_at": now_iso,
        "privacy_accepted_at": now_iso,
        "eligibility_attested_at": now_iso,
    }

    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return user


def authenticate_user(email: str, password: str) -> str | None:
    db = get_database()
    if db is None:
        return create_access_token({"sub": email.lower(), "role": "user"})

    user = db.users.find_one({"email": email.lower()})
    if user is None:
        return None

    if user.get("status") != "active":
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return create_access_token(
        {
            "sub": user["email"],
            "role": user.get("role", "user"),
            "user_id": str(user["_id"]),
        }
    )


def get_user_by_email(email: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    return db.users.find_one({"email": email.lower()})


def get_user_by_id(user_id: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(user_id)
    except Exception:
        return None

    return db.users.find_one({"_id": object_id})