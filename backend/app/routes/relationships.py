from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.relationship_catalog import normalize_relationship_type
from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
)
from app.schemas.relationship import RelationshipCreate, RelationshipResponse
from app.services.relationship_guardrails import RelationshipGuardrailService
from app.services.workspace_access_service import require_workspace_capability

router = APIRouter(prefix="/relationships", tags=["Relationships"])


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
    return has_internal_admin_access(user)


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
    db,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    if not family_id:
        raise HTTPException(status_code=400, detail="family_id is required.")

    if not ObjectId.is_valid(family_id):
        raise HTTPException(status_code=400, detail="Invalid family id.")

    family = db["families"].find_one({"_id": ObjectId(family_id)})
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


def _require_member_access(
    member_id: str,
    db,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ObjectId.is_valid(member_id):
        raise HTTPException(status_code=400, detail="Invalid member id.")

    member = db["family_members"].find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")

    family_id = str(member.get("family_id") or "").strip()
    family = _require_family_access_by_family_id(family_id, db, current_user)
    return member, family


def _require_relationship_access(
    relationship_id: str,
    db,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ObjectId.is_valid(relationship_id):
        raise HTTPException(status_code=400, detail="Invalid relationship_id format")

    relationship = db["relationships"].find_one({"_id": ObjectId(relationship_id)})
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    context = require_workspace_capability(
        current_user,
        family_id=str(relationship.get("family_id") or "").strip(),
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include relationship editing.",
    )
    return relationship, context


@router.post("", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    payload: RelationshipCreate,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    service = RelationshipGuardrailService(db)
    context = require_workspace_capability(
        current_user,
        family_id=payload.family_id,
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include relationship editing.",
    )
    resolved_family_id = str(context["family"].get("_id"))

    created_by = (
        current_user.get("email")
        or current_user.get("username")
        or current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("id")
        or payload.created_by
    )

    guarded_payload = RelationshipCreate(
        family_id=resolved_family_id,
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
        id=str(created["_id"]),
        family_id=created["family_id"],
        source_member_id=created["source_member_id"],
        target_member_id=created["target_member_id"],
        relationship_type=normalize_relationship_type(created["relationship_type"]),
        notes=created.get("notes"),
        created_by=created.get("created_by"),
        created_at=created["created_at"],
    )


@router.get("/family/{family_id}")
async def get_family_relationships(
    family_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include relationship access.",
    )
    resolved_family_id = str(context["family"].get("_id"))

    relationships = []
    cursor = db["relationships"].find({"family_id": resolved_family_id})

    for rel in cursor:
        relationships.append(
            {
                "id": str(rel.get("_id")),
                "family_id": rel.get("family_id"),
                "source_member_id": rel.get("source_member_id"),
                "target_member_id": rel.get("target_member_id"),
                "relationship_type": normalize_relationship_type(
                    rel.get("relationship_type")
                ),
                "notes": rel.get("notes"),
                "created_by": rel.get("created_by"),
                "created_at": rel.get("created_at"),
            }
        )

    return {
        "family_id": resolved_family_id,
        "count": len(relationships),
        "relationships": relationships,
    }


@router.get("/member/{member_id}")
async def get_member_relationships(
    member_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    require_workspace_capability(
        current_user,
        member_id=member_id,
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include relationship access.",
    )

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
        relationships.append(
            {
                "id": str(rel.get("_id")),
                "family_id": rel.get("family_id"),
                "source_member_id": rel.get("source_member_id"),
                "target_member_id": rel.get("target_member_id"),
                "relationship_type": normalize_relationship_type(
                    rel.get("relationship_type")
                ),
                "notes": rel.get("notes"),
                "created_by": rel.get("created_by"),
                "created_at": rel.get("created_at"),
            }
        )

    return {
        "member_id": member_id,
        "count": len(relationships),
        "relationships": relationships,
    }


@router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db

    relationship, _family = _require_relationship_access(relationship_id, db, current_user)

    db["relationships"].delete_one({"_id": ObjectId(relationship_id)})

    deleted_by = (
        current_user.get("email")
        or current_user.get("username")
        or current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("id")
    )

    db["audit_logs"].insert_one(
        {
            "event": "relationship_deleted",
            "relationship_id": relationship_id,
            "family_id": relationship.get("family_id"),
            "deleted_by": deleted_by,
            "created_at": relationship.get("created_at"),
        }
    )

    return {
        "status": "deleted",
        "relationship_id": relationship_id,
    }
