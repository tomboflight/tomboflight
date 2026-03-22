from datetime import UTC, datetime
from typing import Optional

from app.database import get_database
from app.schemas.family import FamilyCreate


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(value).strip().lower()


def list_families(
    *,
    owner_user_id: str | None = None,
    owner_email: str | None = None,
    include_shared: bool = True,
    is_admin: bool = False,
) -> list[dict]:
    db = get_database()
    if db is None:
        return []

    if is_admin:
        return list(db.families.find().sort("created_at", -1))

    owner_email = _normalize_email(owner_email)

    filters = []
    if owner_user_id:
        filters.append({"owner_user_id": owner_user_id})
    if owner_email:
        filters.append({"owner_email": owner_email})

    if include_shared:
        if owner_user_id:
            filters.append({"shared_with_user_ids": owner_user_id})
        if owner_email:
            filters.append({"shared_with_emails": owner_email})

    if not filters:
        return []

    return list(
        db.families.find({"$or": filters}).sort("created_at", -1)
    )


def create_family(
    payload: FamilyCreate,
    *,
    owner_user_id: str | None = None,
    owner_email: str | None = None,
    visibility: str = "private",
    shared_with_user_ids: list[str] | None = None,
    shared_with_emails: list[str] | None = None,
) -> dict:
    db = get_database()
    data = payload.model_dump()

    data["created_at"] = datetime.now(UTC)
    data["owner_user_id"] = owner_user_id
    data["owner_email"] = _normalize_email(owner_email)
    data["visibility"] = visibility
    data["shared_with_user_ids"] = shared_with_user_ids or []
    data["shared_with_emails"] = [
        email for email in (_normalize_email(x) for x in (shared_with_emails or [])) if email
    ]

    if db is None:
        data["_id"] = "local-family-preview"
        return data

    result = db.families.insert_one(data)
    data["_id"] = result.inserted_id
    return data