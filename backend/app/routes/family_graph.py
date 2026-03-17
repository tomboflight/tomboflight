from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_database
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/families", tags=["Family Graph"])


@router.get("/{family_id}/graph")
def get_family_graph(family_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(family_id):
        raise HTTPException(status_code=400, detail="Invalid family id.")

    family = db.families.find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(status_code=404, detail="Family not found.")

    members_cursor = db.family_members.find({"family_id": family_id}).sort("generation", 1)
    relationships_cursor = db.relationships.find({"family_id": family_id})

    members = []
    for member in members_cursor:
        members.append(
            {
                "id": str(member.get("_id")),
                "family_id": member.get("family_id"),
                "first_name": member.get("first_name"),
                "last_name": member.get("last_name"),
                "display_name": f"{member.get('first_name', '')} {member.get('last_name', '')}".strip(),
                "birth_year": member.get("birth_year"),
                "generation": member.get("generation"),
                "father_id": member.get("father_id"),
                "mother_id": member.get("mother_id"),
                "spouse_id": member.get("spouse_id"),
                "bio": member.get("bio"),
                "created_at": member.get("created_at"),
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

    summary = {
        "family_id": str(family.get("_id")),
        "family_name": family.get("family_name"),
        "member_count": len(members),
        "relationship_count": len(relationships),
        "generation_count": (max(generation_values) + 1) if generation_values else 0,
    }

    return {
        "family": {
            "id": str(family.get("_id")),
            "family_name": family.get("family_name"),
            "created_by": family.get("created_by"),
            "description": family.get("description"),
            "created_at": family.get("created_at"),
        },
        "members": members,
        "relationships": relationships,
        "summary": summary,
    }