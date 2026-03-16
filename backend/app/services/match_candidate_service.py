from datetime import UTC, datetime

from bson import ObjectId

from app.database import get_database
from app.schemas.match_candidate import MatchCandidateCreate


class MatchCandidateApprovalError(Exception):
    pass


def list_match_candidates() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.match_candidates.find().sort("created_at", -1))


def create_match_candidate(payload: MatchCandidateCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["created_at"] = datetime.now(UTC).isoformat()

    if db is None:
        data["_id"] = "local-match-candidate-preview"
        return data

    result = db.match_candidates.insert_one(data)
    data["_id"] = result.inserted_id
    return data


def approve_match_candidate(candidate_id: str, decided_by: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(candidate_id)
    except Exception:
        return None

    candidate = db.match_candidates.find_one({"_id": object_id})
    if candidate is None:
        return None

    member_id_a = candidate.get("member_id_a")
    member_id_b = candidate.get("member_id_b")

    if not member_id_a or not ObjectId.is_valid(member_id_a):
        raise MatchCandidateApprovalError(
            "member_id_a is not a valid family member ObjectId."
        )

    if not member_id_b or not ObjectId.is_valid(member_id_b):
        raise MatchCandidateApprovalError(
            "member_id_b is not a valid family member ObjectId."
        )

    member_a_object_id = ObjectId(member_id_a)
    member_b_object_id = ObjectId(member_id_b)

    member_a = db.family_members.find_one({"_id": member_a_object_id})
    member_b = db.family_members.find_one({"_id": member_b_object_id})

    if member_a is None:
        raise MatchCandidateApprovalError("Family member A was not found.")

    if member_b is None:
        raise MatchCandidateApprovalError("Family member B was not found.")

    canonical_person_id = candidate.get("canonical_person_id")

    if canonical_person_id:
        if not ObjectId.is_valid(canonical_person_id):
            raise MatchCandidateApprovalError(
                "canonical_person_id is not a valid ObjectId."
            )

        canonical_person = db.canonical_persons.find_one(
            {"_id": ObjectId(canonical_person_id)}
        )
        if canonical_person is None:
            raise MatchCandidateApprovalError("Canonical person was not found.")
    else:
        seed_member = member_a or member_b

        canonical_person = {
            "display_name": (
                f"{seed_member.get('first_name', '')} "
                f"{seed_member.get('last_name', '')}"
            ).strip(),
            "first_name": seed_member.get("first_name", ""),
            "last_name": seed_member.get("last_name", ""),
            "birth_year": seed_member.get("birth_year"),
            "status": "active",
            "notes": "Auto-created from approved match candidate.",
            "created_at": datetime.now(UTC).isoformat(),
        }
        canonical_result = db.canonical_persons.insert_one(canonical_person)
        canonical_person_id = str(canonical_result.inserted_id)

    db.match_candidates.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "approved",
                "canonical_person_id": canonical_person_id,
                "approved_by": decided_by,
                "approved_at": datetime.now(UTC).isoformat(),
            }
        },
    )

    existing_link_a = db.identity_links.find_one(
        {
            "family_member_id": member_id_a,
            "canonical_person_id": canonical_person_id,
        }
    )
    if existing_link_a is None:
        db.identity_links.insert_one(
            {
                "family_member_id": member_id_a,
                "canonical_person_id": canonical_person_id,
                "link_status": "linked",
                "linked_by": decided_by,
                "notes": "Created by approved match candidate.",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    existing_link_b = db.identity_links.find_one(
        {
            "family_member_id": member_id_b,
            "canonical_person_id": canonical_person_id,
        }
    )
    if existing_link_b is None:
        db.identity_links.insert_one(
            {
                "family_member_id": member_id_b,
                "canonical_person_id": canonical_person_id,
                "link_status": "linked",
                "linked_by": decided_by,
                "notes": "Created by approved match candidate.",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    return db.match_candidates.find_one({"_id": object_id})


def reject_match_candidate(candidate_id: str, decided_by: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(candidate_id)
    except Exception:
        return None

    candidate = db.match_candidates.find_one({"_id": object_id})
    if candidate is None:
        return None

    db.match_candidates.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "rejected",
                "rejected_by": decided_by,
                "rejected_at": datetime.now(UTC).isoformat(),
            }
        },
    )

    return db.match_candidates.find_one({"_id": object_id})