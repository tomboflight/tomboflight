from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.metadata import apply_create_metadata, apply_update_metadata
from app.database import get_database
from app.dependencies.auth import (
    enforce_limit,
    get_current_user,
    has_internal_admin_access,
)
from app.core.relationship_catalog import (
    PARENT_RELATIONSHIP_TYPES,
    PARTNER_RELATIONSHIP_TYPES,
    normalize_relationship_type,
)
from app.schemas.family_member import FamilyMemberCreate, FamilyMemberUpdate
from app.schemas.relationship import RelationshipCreate
from app.services.audit_log_service import create_audit_log
from app.services.family_placement_service import rebuild_family_placement
from app.services.matching import generate_match_candidates_for_member
from app.services.relationship_guardrails import RelationshipGuardrailService
from app.services.workspace_access_service import (
    family_is_visible_to_user,
    list_accessible_families_for_user,
    require_workspace_capability,
    require_workspace_member_role,
)

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


def _family_id_candidates(family_id: str) -> list[Any]:
    candidates: list[Any] = [family_id]
    if ObjectId.is_valid(family_id):
        candidates.append(ObjectId(family_id))
    return candidates


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

    if has_internal_admin_access(current_user):
        return family

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not family_is_visible_to_user(
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
        "placement_status": member.get("placement_status") or "unplaced",
        "father_id": member.get("father_id"),
        "mother_id": member.get("mother_id"),
        "spouse_id": member.get("spouse_id"),
        "bio": member.get("bio"),
        "created_at": member.get("created_at"),
        "is_verified": member.get("is_verified"),
        "verification_status": member.get("verification_status"),
        "approved_photo_upload_id": member.get("approved_photo_upload_id"),
        "pending_photo_upload_id": member.get("pending_photo_upload_id"),
        "identity_matching_consent": bool(member.get("identity_matching_consent")),
        "account_required": bool(member.get("account_required")),
        "invite_email": member.get("invite_email"),
        "account_member_role": member.get("account_member_role") or "viewer",
    }


def _display_name(member: dict[str, Any]) -> str:
    first_name = str(member.get("first_name") or "").strip()
    last_name = str(member.get("last_name") or "").strip()
    joined = f"{first_name} {last_name}".strip()
    return joined or "Unknown Member"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@router.get("-index")
def list_family_members_index(current_user: dict[str, Any] = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if has_internal_admin_access(current_user):
        cursor = db.family_members.find().sort("created_at", 1)
        return [_serialize_member(member) for member in cursor]

    visible_family_ids = [
        str(family.get("_id"))
        for family in list_accessible_families_for_user(
            current_user,
            capabilities=("can_build_family_tree", "can_open_family_intake"),
        )
    ]

    if not visible_family_ids:
        return []

    family_id_candidates: list[Any] = []
    for family_id in visible_family_ids:
        family_id_candidates.extend(_family_id_candidates(family_id))

    cursor = db.family_members.find(
        {"family_id": {"$in": family_id_candidates}}
    ).sort("created_at", 1)

    return [_serialize_member(member) for member in cursor]


@router.post("")
def create_family_member(
    payload: FamilyMemberCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    family_id = str(payload.family_id or "").strip()
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include family member editing.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for family member edits.",
    )

    user_id = _current_user_id(current_user)

    payload_data = payload.model_dump()
    payload_data["family_id"] = str(context["family"].get("_id"))
    relationship_mode = str(payload_data.pop("relationship_mode") or "narrative").strip().lower()
    relationship_privacy_scope = str(
        payload_data.pop("privacy_scope") or "household_private"
    ).strip().lower()
    father_relationship_type = normalize_relationship_type(
        payload_data.pop("father_relationship_type")
    )
    mother_relationship_type = normalize_relationship_type(
        payload_data.pop("mother_relationship_type")
    )
    partner_relationship_type = normalize_relationship_type(
        payload_data.pop("partner_relationship_type")
    )
    if bool(payload_data.get("account_required")) and not str(
        payload_data.get("invite_email") or ""
    ).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An invite email is required when this person needs an account.",
        )
    if payload_data.get("generation") is not None or bool(
        payload_data.get("generation_locked")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Generation and placement locks are calculated from relationships "
                "and cannot be supplied when creating a family member."
            ),
        )
    if relationship_mode != "narrative":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Verified relationships require approved evidence and must be "
                "created through the guided relationship workflow."
            ),
        )
    if father_relationship_type not in PARENT_RELATIONSHIP_TYPES:
        raise HTTPException(status_code=400, detail="Invalid father/parent relationship type.")
    if mother_relationship_type not in PARENT_RELATIONSHIP_TYPES:
        raise HTTPException(status_code=400, detail="Invalid mother/parent relationship type.")
    if partner_relationship_type not in PARTNER_RELATIONSHIP_TYPES:
        raise HTTPException(status_code=400, detail="Invalid spouse/partner relationship type.")
    payload_data["generation"] = 0
    payload_data["generation_locked"] = False

    current_member_count = db.family_members.count_documents(
        {"family_id": {"$in": _family_id_candidates(payload_data["family_id"])}}
    )
    enforce_limit("family_members", current_member_count + 1, context=context)

    payload_data = apply_create_metadata(payload_data, user_id)
    result = db.family_members.insert_one(payload_data)

    member_id = str(result.inserted_id)
    relationship_service = RelationshipGuardrailService(db)
    created_relationship_ids: list[str] = []
    requested_relationships = [
        (payload_data.get("father_id"), father_relationship_type, "father/parent"),
        (payload_data.get("mother_id"), mother_relationship_type, "mother/parent"),
    ]
    if payload_data.get("spouse_id"):
        requested_relationships.append(
            (payload_data.get("spouse_id"), partner_relationship_type, "spouse/partner")
        )

    try:
        for related_member_id, relationship_type, label in requested_relationships:
            related_id = str(related_member_id or "").strip()
            if not related_id:
                continue
            source_member_id = (
                member_id if relationship_type in PARTNER_RELATIONSHIP_TYPES else related_id
            )
            target_member_id = (
                related_id if relationship_type in PARTNER_RELATIONSHIP_TYPES else member_id
            )
            created_relationship = relationship_service.create_relationship(
                RelationshipCreate(
                    family_id=payload_data["family_id"],
                    source_member_id=source_member_id,
                    target_member_id=target_member_id,
                    relationship_type=relationship_type,
                    relationship_mode="narrative",
                    status_marker="narrative",
                    privacy_scope=relationship_privacy_scope,
                    relationship_label=label,
                    created_by=user_id,
                )
            )
            created_relationship_ids.append(str(created_relationship.get("_id") or ""))
        if not requested_relationships or not created_relationship_ids:
            rebuild_family_placement(db, payload_data["family_id"])
    except Exception:
        for relationship_id in created_relationship_ids:
            if ObjectId.is_valid(relationship_id):
                db.relationships.delete_one({"_id": ObjectId(relationship_id)})
        db.family_members.delete_one({"_id": result.inserted_id})
        rebuild_family_placement(db, payload_data["family_id"])
        raise

    create_audit_log(
        action="family_member_created",
        actor_user_id=user_id,
        entity_type="family_member",
        entity_id=member_id,
        details={
            "family_id": payload_data["family_id"],
            "payload_keys": list(payload_data.keys()),
            "relationship_ids": created_relationship_ids,
        },
    )

    created_candidates = (
        generate_match_candidates_for_member(member_id, user_id)
        if bool(payload_data.get("identity_matching_consent"))
        else []
    )

    return {
        "message": "Family member created successfully.",
        "family_member_id": member_id,
        "match_candidates_created": created_candidates,
    }


@router.put("/{member_id}")
def update_family_member(
    member_id: str,
    payload: FamilyMemberUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    context = require_workspace_capability(
        current_user,
        member_id=member_id,
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include family member editing.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for family member edits.",
    )
    existing = context["member"]

    user_id = _current_user_id(current_user)
    payload_data = payload.model_dump(exclude_unset=True)
    if "generation" in payload_data or "generation_locked" in payload_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Generation and placement locks are calculated from relationships "
                "and cannot be edited directly."
            ),
        )
    effective_account_required = bool(
        payload_data.get("account_required", existing.get("account_required"))
    )
    effective_invite_email = str(
        payload_data.get("invite_email", existing.get("invite_email")) or ""
    ).strip()
    if effective_account_required and not effective_invite_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An invite email is required when this person needs an account.",
        )
    payload_data = apply_update_metadata(payload_data, user_id)

    db.family_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": payload_data},
    )

    create_audit_log(
        action="family_member_updated",
        actor_user_id=user_id,
        entity_type="family_member",
        entity_id=member_id,
        details={"updated_keys": list(payload_data.keys())},
    )

    created_candidates = (
        generate_match_candidates_for_member(member_id, user_id)
        if bool(payload_data.get("identity_matching_consent") or existing.get("identity_matching_consent"))
        else []
    )

    return {
        "message": "Family member updated successfully.",
        "family_member_id": member_id,
        "match_candidates_created": created_candidates,
    }


@router.delete("/{member_id}")
def delete_family_member(
    member_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    context = require_workspace_capability(
        current_user,
        member_id=member_id,
        capabilities=("can_build_family_tree", "can_open_family_intake"),
        detail="Your active package does not include family member editing.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager"),
        detail="Your role cannot remove family members.",
    )
    existing = context["member"]

    relationship_count = db.relationships.count_documents(
        {
            "$or": [
                {"source_member_id": member_id},
                {"target_member_id": member_id},
            ]
        }
    )

    if relationship_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete member while {relationship_count} relationship(s) still reference this record. "
                "Delete those relationships first."
            ),
        )

    user_id = _current_user_id(current_user)

    db.family_members.delete_one({"_id": ObjectId(member_id)})

    create_audit_log(
        action="family_member_deleted",
        actor_user_id=user_id,
        entity_type="family_member",
        entity_id=member_id,
        details={
            "family_id": str(existing.get("family_id") or ""),
            "display_name": _display_name(existing),
        },
    )

    return {
        "status": "deleted",
        "family_member_id": member_id,
        "display_name": _display_name(existing),
    }
