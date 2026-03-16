from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies.auth import get_current_user
from app.schemas.relationship import RelationshipCreate, RelationshipResponse
from app.services.relationship_guardrails import RelationshipGuardrailService


router = APIRouter(prefix="/relationships", tags=["Relationships"])


@router.post("", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    payload: RelationshipCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    service = RelationshipGuardrailService(db)

    created_by = (
        current_user.get("email")
        or current_user.get("username")
        or current_user.get("id")
        or payload.created_by
    )

    guarded_payload = RelationshipCreate(
        family_id=payload.family_id,
        source_member_id=payload.source_member_id,
        target_member_id=payload.target_member_id,
        relationship_type=payload.relationship_type,
        notes=payload.notes,
        created_by=created_by,
    )

    created = service.create_relationship(guarded_payload)

    db["audit_logs"].insert_one(
        {
            "event": "relationship_created",
            "relationship_id": created["_id"],
            "family_id": created["family_id"],
            "source_member_id": created["source_member_id"],
            "target_member_id": created["target_member_id"],
            "created_by": created_by,
            "created_at": created["created_at"],
        }
    )

    return RelationshipResponse(
        id=created["_id"],
        family_id=created["family_id"],
        source_member_id=created["source_member_id"],
        target_member_id=created["target_member_id"],
        relationship_type=created["relationship_type"],
        notes=created.get("notes"),
        created_by=created.get("created_by"),
        created_at=created["created_at"],
    )


@router.get("/family/{family_id}")
async def get_family_relationships(
    family_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db

    relationships = []
    cursor = db["relationships"].find({"family_id": family_id})

    for rel in cursor:
        rel["_id"] = str(rel["_id"])
        relationships.append(rel)

    return {
        "family_id": family_id,
        "count": len(relationships),
        "relationships": relationships,
    }


@router.get("/member/{member_id}")
async def get_member_relationships(
    member_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db

    relationships = []
    cursor = db["relationships"].find(
        {
            "$or": [
                {"source_member_id": member_id},
                {"target_member_id": member_id},
            ]
        }
    )

    for rel in cursor:
        rel["_id"] = str(rel["_id"])
        relationships.append(rel)

    return {
        "member_id": member_id,
        "count": len(relationships),
        "relationships": relationships,
    }


@router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db

    try:
        object_id = ObjectId(relationship_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid relationship_id format")

    relationship = db["relationships"].find_one({"_id": object_id})

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    db["relationships"].delete_one({"_id": object_id})

    db["audit_logs"].insert_one(
        {
            "event": "relationship_deleted",
            "relationship_id": relationship_id,
            "family_id": relationship.get("family_id"),
            "deleted_by": current_user.get("email")
            or current_user.get("username")
            or current_user.get("id"),
            "created_at": relationship.get("created_at"),
        }
    )

    return {
        "status": "deleted",
        "relationship_id": relationship_id,
    }