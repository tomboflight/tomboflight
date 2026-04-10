from datetime import UTC, datetime

from bson import ObjectId

from app.core.state_catalog import normalize_approval_state
from app.database import get_database
from app.schemas.match_candidate import MatchCandidateCreate
from app.services.approval import ApprovalError, approve_match_candidate as approve_candidate_record


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
    source_member_id = str(
        data.get("source_member_id") or data.get("member_id_a") or ""
    ).strip()
    target_member_id = str(
        data.get("target_member_id") or data.get("member_id_b") or ""
    ).strip()
    data["source_member_id"] = source_member_id
    data["target_member_id"] = target_member_id
    data["member_id_a"] = source_member_id
    data["member_id_b"] = target_member_id
    data["status"] = normalize_approval_state(data.get("status"), default="pending")
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
        approve_candidate_record(candidate_id=candidate_id, actor_user_id=decided_by)
    except ApprovalError as exc:
        raise MatchCandidateApprovalError(str(exc)) from exc
    except Exception:
        return None

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

    if normalize_approval_state(candidate.get("status")) != "pending":
        raise MatchCandidateApprovalError(
            "Only pending match candidates can be rejected."
        )

    db.match_candidates.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": normalize_approval_state("rejected"),
                "rejected_by": decided_by,
                "rejected_at": datetime.now(UTC).isoformat(),
            }
        },
    )

    return db.match_candidates.find_one({"_id": object_id})
