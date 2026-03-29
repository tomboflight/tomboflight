from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database
from app.dependencies.auth import get_current_user, require_any_package_capability

router = APIRouter(prefix="/families", tags=["Family Graph"])

INTERNAL_ADMIN_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
}


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_email(user: dict[str, Any]) -> str:
    raw_email = user.get("email")
    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user email is missing.",
        )
    return str(raw_email).strip().lower()


def _current_user_display_name(user: dict[str, Any]) -> str:
    raw_name = user.get("full_name") or user.get("name") or ""
    return str(raw_name).strip()


def _normalize_value(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_admin(user: dict[str, Any]) -> bool:
    values = {
        _normalize_value(user.get("role")),
        _normalize_value(user.get("access_tier")),
        _normalize_value(user.get("department_role")),
    }
    return any(value in INTERNAL_ADMIN_KEYS for value in values if value)


def _family_is_visible_to_user(
    family: dict[str, Any],
    current_user_id: str,
    current_user_email: str,
    current_user_name: str,
) -> bool:
    owner_user_id = str(family.get("owner_user_id") or "").strip()
    owner_email = str(family.get("owner_email") or "").strip().lower()

    shared_with_user_ids = [
        str(value).strip()
        for value in (family.get("shared_with_user_ids") or [])
        if value is not None
    ]
    shared_with_emails = [
        str(value).strip().lower()
        for value in (family.get("shared_with_emails") or [])
        if value is not None
    ]

    if owner_user_id and owner_user_id == current_user_id:
        return True

    if owner_email and owner_email == current_user_email:
        return True

    if current_user_id in shared_with_user_ids:
        return True

    if current_user_email in shared_with_emails:
        return True

    # Backward-compatible fallback for older family records
    if not owner_user_id and not owner_email:
        created_by = str(family.get("created_by") or "").strip()
        if created_by and (
            created_by == current_user_name or created_by.lower() == current_user_email
        ):
            return True

    return False


@router.get("/{family_id}/graph")
def get_family_graph(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_any_package_capability(
        current_user,
        "can_build_family_tree",
        "can_upload_verification_docs",
        "can_upload_portraits",
        detail="Your active package does not include access to this family workspace.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(family_id):
        raise HTTPException(status_code=400, detail="Invalid family id.")

    family = db.families.find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(status_code=404, detail="Family not found.")

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not _is_admin(current_user) and not _family_is_visible_to_user(
        family=family,
        current_user_id=current_user_id,
        current_user_email=current_user_email,
        current_user_name=current_user_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this family graph.",
        )

    members_cursor = db.family_members.find({"family_id": family_id}).sort("generation", 1)
    relationships_cursor = db.relationships.find({"family_id": family_id})

    members = []
    for member in members_cursor:
        first_name = member.get("first_name")
        last_name = member.get("last_name")
        display_name = f"{first_name or ''} {last_name or ''}".strip()

        members.append(
            {
                "id": str(member.get("_id")),
                "family_id": member.get("family_id"),
                "first_name": first_name,
                "last_name": last_name,
                "display_name": display_name,
                "birth_year": member.get("birth_year"),
                "generation": member.get("generation"),
                "father_id": member.get("father_id"),
                "mother_id": member.get("mother_id"),
                "spouse_id": member.get("spouse_id"),
                "bio": member.get("bio"),
                "created_at": member.get("created_at"),
                "updated_at": member.get("updated_at"),
                "created_by": member.get("created_by"),
                "updated_by": member.get("updated_by"),
                "is_verified": bool(member.get("is_verified", False)),
                "verification_status": member.get("verification_status"),
                "verification_method": member.get("verification_method"),
                "verified_by": member.get("verified_by"),
                "verified_at": member.get("verified_at"),
                "verification_notes": member.get("verification_notes"),
            }
        )

    relationships = []
    for rel in relationships_cursor:
        relationships.append(
            {
                "id": str(rel.get("_id")),
                "family_id": rel.get("family_id"),
                "source_member_id": rel.get("source_member_id"),
                "target_member_id": rel.get("target_member_id"),
                "relationship_type": rel.get("relationship_type"),
                "notes": rel.get("notes"),
                "created_by": rel.get("created_by"),
                "created_at": rel.get("created_at"),
            }
        )

    generation_values = [
        member["generation"]
        for member in members
        if isinstance(member.get("generation"), int)
    ]

    verified_member_count = sum(
        1 for member in members if member.get("is_verified") is True
    )

    summary = {
        "family_id": str(family.get("_id")),
        "family_name": family.get("family_name"),
        "member_count": len(members),
        "relationship_count": len(relationships),
        "generation_count": (max(generation_values) + 1) if generation_values else 0,
        "verified_member_count": verified_member_count,
    }

    return {
        "family": {
            "id": str(family.get("_id")),
            "family_name": family.get("family_name"),
            "created_by": family.get("created_by"),
            "description": family.get("description"),
            "created_at": family.get("created_at"),
            "owner_user_id": family.get("owner_user_id"),
            "owner_email": family.get("owner_email"),
            "visibility": family.get("visibility", "private"),
        },
        "members": members,
        "relationships": relationships,
        "summary": summary,
    }
