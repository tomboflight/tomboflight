from typing import Any, Dict

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.metadata import apply_create_metadata, apply_update_metadata
from app.database import get_database
from app.dependencies.auth import get_current_user
from app.services.audit_log_service import create_audit_log
from app.services.matching import generate_match_candidates_for_member

router = APIRouter(prefix="/family-members", tags=["family_members"])


@router.get("-index")
def list_family_members_index(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    members = []
    cursor = db.family_members.find().sort("created_at", 1)

    for member in cursor:
      members.append(
          {
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
      )

    return members


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