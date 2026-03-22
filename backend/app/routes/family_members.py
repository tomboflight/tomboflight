from typing import Any, Dict

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.metadata import apply_create_metadata, apply_update_metadata
from app.database import get_database
from app.dependencies.auth import get_current_user
from app.services.audit_log_service import create_audit_log
from app.services.matching import generate_match_candidates_for_member

router = APIRouter(prefix="/family-members", tags=["family_members"])


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


def _is_admin(user: dict[str, Any]) -> bool:
    return str(user.get("role", "")).strip().lower() == "admin"


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


def _require_family_access_by_family_id(
    family_id: str,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not family_id:
        raise HTTPException(status_code=400, detail="family_id is required.")

    if not ObjectId.is_valid(family_id):
        raise HTTPException(status_code=400, detail="Invalid family id.")

    family = db.families.find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(status_code=404, detail="Family not found.")

    if _is_admin(current_user):
        return family

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not _family_is_visible_to_user(
        family=family,
        current_user_id=current_user_id,
        current_user_email=current_user_email,
        current_user_name=current_user_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this family.",
        )

    return family


def _require_family_access_for_member(
    member_id: str,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(member_id):
        raise HTTPException(status_code=400, detail="Invalid family member id.")

    member = db.family_members.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")

    family_id = str(member.get("family_id") or "").strip()
    family = _require_family_access_by_family_id(family_id, current_user)

    return member, family


def _serialize_member(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(member.get("_id")),
        "family_id": member.get("family_id"),
        "first_name": member.get("first_name"),
        "last_name": member.get("last_name"),
        "birth_year": member.get("birth_year"),
        "generation": member.get("generation"),
        "father_id": member.get("father_id"),
        "mother_id": member.get("mother_id"),
        "spouse_id": member.get("spouse_id"),
        "bio": member.get("bio"),
        "created_at": member.get("created_at"),
    }


@router.get("-index")
def list_family_members_index(current_user: dict[str, Any] = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if _is_admin(current_user):
        cursor = db.family_members.find().sort("created_at", 1)
        return [_serialize_member(member) for member in cursor]

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    visible_family_ids: list[str] = []
    family_cursor = db.families.find()

    for family in family_cursor:
        if _family_is_visible_to_user(
            family=family,
            current_user_id=current_user_id,
            current_user_email=current_user_email,
            current_user_name=current_user_name,
        ):
            visible_family_ids.append(str(family.get("_id")))

    if not visible_family_ids:
        return []

    cursor = db.family_members.find(
        {"family_id": {"$in": visible_family_ids}}
    ).sort("created_at", 1)

    return [_serialize_member(member) for member in cursor]


@router.post("")
def create_family_member(
    payload: Dict[str, Any],
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    family_id = str(payload.get("family_id") or "").strip()
    _require_family_access_by_family_id(family_id, current_user)

    user_id = _current_user_id(current_user)

    payload = dict(payload)
    payload["family_id"] = family_id

    payload = apply_create_metadata(payload, user_id)
    result = db.family_members.insert_one(payload)

    member_id = str(result.inserted_id)

    create_audit_log(
        action="family_member_created",
        actor_user_id=user_id,
        entity_type="family_member",
        entity_id=member_id,
        details={
            "family_id": family_id,
            "payload_keys": list(payload.keys()),
        },
    )

    created_candidates = generate_match_candidates_for_member(member_id, user_id)

    return {
        "message": "Family member created successfully.",
        "family_member_id": member_id,
        "match_candidates_created": created_candidates,
    }


@router.put("/{member_id}")
def update_family_member(
    member_id: str,
    payload: Dict[str, Any],
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    existing, _family = _require_family_access_for_member(member_id, current_user)

    if "family_id" in payload:
        incoming_family_id = str(payload.get("family_id") or "").strip()
        existing_family_id = str(existing.get("family_id") or "").strip()

        if incoming_family_id and incoming_family_id != existing_family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="family_id cannot be changed through this endpoint.",
            )

    user_id = _current_user_id(current_user)
    payload = apply_update_metadata(dict(payload), user_id)

    db.family_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": payload},
    )

    create_audit_log(
        action="family_member_updated",
        actor_user_id=user_id,
        entity_type="family_member",
        entity_id=member_id,
        details={"updated_keys": list(payload.keys())},
    )

    created_candidates = generate_match_candidates_for_member(member_id, user_id)

    return {
        "message": "Family member updated successfully.",
        "family_member_id": member_id,
        "match_candidates_created": created_candidates,
    }