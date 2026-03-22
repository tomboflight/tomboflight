from datetime import UTC, datetime

from app.database import get_database
from app.schemas.family_member import FamilyMemberCreate


def list_family_members(
    *,
    family_ids: list[str] | None = None,
    is_admin: bool = False,
) -> list[dict]:
    db = get_database()
    if db is None:
        return []

    if is_admin:
        return list(
            db.family_members.find().sort(
                [("generation", 1), ("created_at", 1)]
            )
        )

    if not family_ids:
        return []

    return list(
        db.family_members.find({"family_id": {"$in": family_ids}}).sort(
            [("generation", 1), ("created_at", 1)]
        )
    )


def create_family_member(
    payload: FamilyMemberCreate,
    *,
    created_by_user_id: str | None = None,
) -> dict:
    db = get_database()
    data = payload.model_dump()

    data["created_at"] = datetime.now(UTC)
    if created_by_user_id:
        data["created_by_user_id"] = created_by_user_id

    if db is None:
        data["_id"] = "local-family-member-preview"
        return data

    result = db.family_members.insert_one(data)
    data["_id"] = result.inserted_id
    return data