from typing import Any, Dict, Optional

from bson import ObjectId

from app.core.metadata import apply_create_metadata, apply_update_metadata
from app.database import get_database
from app.services.audit_log_service import create_audit_log


class ApprovalError(Exception):
    pass


def get_existing_identity_link(member_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    if db is None:
        raise ApprovalError("Database is not connected.")

    return db.identity_links.find_one({"family_member_id": member_id})


def get_or_create_canonical_person(
    source_member_id: str,
    target_member_id: str,
    actor_user_id: Optional[str] = None,
) -> str:
    db = get_database()
    if db is None:
        raise ApprovalError("Database is not connected.")

    source_link = get_existing_identity_link(source_member_id)
    target_link = get_existing_identity_link(target_member_id)

    if source_link and target_link:
        if source_link["canonical_person_id"] != target_link["canonical_person_id"]:
            raise ApprovalError(
                "Members already belong to different canonical persons. Manual merge flow required."
            )
        return source_link["canonical_person_id"]

    if source_link:
        return source_link["canonical_person_id"]

    if target_link:
        return target_link["canonical_person_id"]

    canonical_payload = {
        "status": "active",
        "notes": "Auto-created during match approval",
    }
    canonical_payload = apply_create_metadata(canonical_payload, actor_user_id)

    result = db.canonical_persons.insert_one(canonical_payload)
    return str(result.inserted_id)


def ensure_identity_link(member_id: str, canonical_person_id: str, actor_user_id: Optional[str] = None) -> None:
    db = get_database()
    if db is None:
        raise ApprovalError("Database is not connected.")

    existing = get_existing_identity_link(member_id)

    if existing:
        if existing["canonical_person_id"] != canonical_person_id:
            raise ApprovalError("Member already linked to a different canonical person.")
        return

    payload = {
        "family_member_id": member_id,
        "canonical_person_id": canonical_person_id,
        "status": "active",
    }
    payload = apply_create_metadata(payload, actor_user_id)
    db.identity_links.insert_one(payload)


def approve_match_candidate(candidate_id: str, actor_user_id: Optional[str] = None) -> Dict[str, Any]:
    db = get_database()
    if db is None:
        raise ApprovalError("Database is not connected.")

    if not ObjectId.is_valid(candidate_id):
        raise ApprovalError("Invalid candidate id.")

    candidate = db.match_candidates.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        raise ApprovalError("Match candidate not found.")

    if candidate.get("status") != "pending":
        raise ApprovalError("Only pending match candidates can be approved.")

    source_member_id = candidate.get("source_member_id")
    target_member_id = candidate.get("target_member_id")

    if not source_member_id or not target_member_id:
        raise ApprovalError("Candidate is missing member references.")

    if not ObjectId.is_valid(source_member_id) or not ObjectId.is_valid(target_member_id):
        raise ApprovalError("Candidate contains invalid family member ids.")

    source_member = db.family_members.find_one({"_id": ObjectId(source_member_id)})
    target_member = db.family_members.find_one({"_id": ObjectId(target_member_id)})

    if not source_member or not target_member:
        raise ApprovalError("One or both family member records no longer exist.")

    canonical_person_id = get_or_create_canonical_person(
        source_member_id=source_member_id,
        target_member_id=target_member_id,
        actor_user_id=actor_user_id,
    )

    ensure_identity_link(source_member_id, canonical_person_id, actor_user_id)
    ensure_identity_link(target_member_id, canonical_person_id, actor_user_id)

    update_data = {
        "status": "approved",
        "approved_by": actor_user_id,
        "canonical_person_id": canonical_person_id,
    }
    update_data = apply_update_metadata(update_data, actor_user_id)

    db.match_candidates.update_one(
        {"_id": ObjectId(candidate_id)},
        {"$set": update_data},
    )

    create_audit_log(
        action="match_candidate_approved",
        actor_user_id=actor_user_id,
        entity_type="match_candidate",
        entity_id=candidate_id,
        details={
            "source_member_id": source_member_id,
            "target_member_id": target_member_id,
            "canonical_person_id": canonical_person_id,
        },
    )

    return {
        "message": "Match candidate approved successfully.",
        "candidate_id": candidate_id,
        "canonical_person_id": canonical_person_id,
        "source_member_id": source_member_id,
        "target_member_id": target_member_id,
    }