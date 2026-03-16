from typing import Any, Dict

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.metadata import apply_create_metadata, apply_update_metadata
from app.database import get_database
from app.dependencies.auth import get_current_user
from app.services.audit_log_service import create_audit_log
from app.services.matching import generate_match_candidates_for_member

router = APIRouter(prefix="/family-members", tags=["family_members"])


@router.post("")
def create_family_member(payload: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    user_id = str(current_user.get("_id")) if current_user.get("_id") else None

    payload = apply_create_metadata(payload, user_id)
    result = db.family_members.insert_one(payload)

    member_id = str(result.inserted_id)

    create_audit_log(
        action="family_member_created",
        actor_user_id=user_id,
        entity_type="family_member",
        entity_id=member_id,
        details={"payload_keys": list(payload.keys())},
    )

    created_candidates = generate_match_candidates_for_member(member_id, user_id)

    return {
        "message": "Family member created successfully.",
        "family_member_id": member_id,
        "match_candidates_created": created_candidates,
    }


@router.put("/{member_id}")
def update_family_member(member_id: str, payload: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(member_id):
        raise HTTPException(status_code=400, detail="Invalid family member id.")

    existing = db.family_members.find_one({"_id": ObjectId(member_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Family member not found.")

    user_id = str(current_user.get("_id")) if current_user.get("_id") else None
    payload = apply_update_metadata(payload, user_id)

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