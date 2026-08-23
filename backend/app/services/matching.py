from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from app.core.metadata import apply_create_metadata
from app.database import get_database
from app.services.audit_log_service import create_audit_log


MATCH_THRESHOLD = 0.78
AUTO_REVIEW_STATUS = "pending"


def normalize_string(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def normalize_member(member: Dict[str, Any]) -> Dict[str, Any]:
    first_name = normalize_string(member.get("first_name"))
    middle_name = normalize_string(member.get("middle_name"))
    last_name = normalize_string(member.get("last_name"))
    full_name = normalize_string(
        f"{member.get('first_name', '')} "
        f"{member.get('middle_name', '')} "
        f"{member.get('last_name', '')}"
    )

    return {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "full_name": full_name,
        "birth_date": normalize_string(member.get("birth_date")),
        "birth_year": normalize_string(member.get("birth_year")),
        "gender": normalize_string(member.get("gender")),
        "household_id": str(member.get("household_id")) if member.get("household_id") else "",
        "father_name": normalize_string(member.get("father_name")),
        "mother_name": normalize_string(member.get("mother_name")),
        "spouse_name": normalize_string(member.get("spouse_name")),
    }


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def score_match(member_a: Dict[str, Any], member_b: Dict[str, Any]) -> Tuple[float, List[str]]:
    a = normalize_member(member_a)
    b = normalize_member(member_b)

    score = 0.0
    reasons: List[str] = []

    full_name_score = similarity(a["full_name"], b["full_name"])
    if full_name_score >= 0.90:
        score += 0.45
        reasons.append("Very similar full name")
    elif full_name_score >= 0.78:
        score += 0.30
        reasons.append("Similar full name")

    last_name_score = similarity(a["last_name"], b["last_name"])
    if last_name_score >= 0.95 and a["last_name"]:
        score += 0.15
        reasons.append("Matching or near-matching last name")

    first_name_score = similarity(a["first_name"], b["first_name"])
    if first_name_score >= 0.90 and a["first_name"]:
        score += 0.15
        reasons.append("Matching or near-matching first name")

    if a["birth_date"] and b["birth_date"] and a["birth_date"] == b["birth_date"]:
        score += 0.20
        reasons.append("Exact matching birth date")
    elif a["birth_year"] and b["birth_year"] and a["birth_year"] == b["birth_year"]:
        score += 0.12
        reasons.append("Matching birth year")

    if a["gender"] and b["gender"] and a["gender"] == b["gender"]:
        score += 0.05
        reasons.append("Matching gender")

    if a["father_name"] and b["father_name"] and similarity(a["father_name"], b["father_name"]) >= 0.90:
        score += 0.10
        reasons.append("Very similar father name")

    if a["mother_name"] and b["mother_name"] and similarity(a["mother_name"], b["mother_name"]) >= 0.90:
        score += 0.10
        reasons.append("Very similar mother name")

    if a["spouse_name"] and b["spouse_name"] and similarity(a["spouse_name"], b["spouse_name"]) >= 0.90:
        score += 0.08
        reasons.append("Very similar spouse name")

    if a["household_id"] and b["household_id"] and a["household_id"] == b["household_id"]:
        score += 0.05
        reasons.append("Same household")

    if score > 1.0:
        score = 1.0

    return score, reasons


def candidate_pair_exists(member_a_id: str, member_b_id: str) -> bool:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    existing = db.match_candidates.find_one(
        {
            "$or": [
                {
                    "source_member_id": member_a_id,
                    "target_member_id": member_b_id,
                    "status": {"$in": ["pending", "approved"]},
                },
                {
                    "source_member_id": member_b_id,
                    "target_member_id": member_a_id,
                    "status": {"$in": ["pending", "approved"]},
                },
            ]
        }
    )
    return existing is not None


def create_match_candidate(
    source_member: Dict[str, Any],
    target_member: Dict[str, Any],
    score: float,
    reasons: List[str],
    created_by: Optional[str] = None,
) -> Optional[str]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    source_id = str(source_member["_id"])
    target_id = str(target_member["_id"])

    if source_id == target_id:
        return None

    if candidate_pair_exists(source_id, target_id):
        return None

    payload = {
        "source_member_id": source_id,
        "target_member_id": target_id,
        "status": AUTO_REVIEW_STATUS,
        "score": round(score, 4),
        "reasons": reasons,
        "review_notes": "",
    }

    payload = apply_create_metadata(payload, created_by)
    result = db.match_candidates.insert_one(payload)

    create_audit_log(
        action="match_candidate_auto_created",
        actor_user_id=created_by,
        entity_type="match_candidate",
        entity_id=str(result.inserted_id),
        details={
            "source_member_id": source_id,
            "target_member_id": target_id,
            "score": round(score, 4),
            "reasons": reasons,
        },
    )

    return str(result.inserted_id)


def generate_match_candidates_for_member(member_id: str, actor_user_id: Optional[str] = None) -> List[str]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    if not ObjectId.is_valid(member_id):
        return []

    current_member = db.family_members.find_one({"_id": ObjectId(member_id)})
    if not current_member:
        return []
    if not bool(current_member.get("identity_matching_consent")):
        return []

    created_candidate_ids: List[str] = []

    others = db.family_members.find(
        {
            "_id": {"$ne": ObjectId(member_id)},
            "identity_matching_consent": True,
        }
    )

    for other in others:
        if not _members_share_authorized_identity_scope(db, current_member, other):
            continue
        score, reasons = score_match(current_member, other)
        if score >= MATCH_THRESHOLD:
            candidate_id = create_match_candidate(
                source_member=current_member,
                target_member=other,
                score=score,
                reasons=reasons,
                created_by=actor_user_id,
            )
            if candidate_id:
                created_candidate_ids.append(candidate_id)

    return created_candidate_ids


def _members_share_authorized_identity_scope(
    db: Any,
    member_a: Dict[str, Any],
    member_b: Dict[str, Any],
) -> bool:
    family_a_id = str(member_a.get("family_id") or "").strip()
    family_b_id = str(member_b.get("family_id") or "").strip()
    if not family_a_id or not family_b_id:
        return False
    if family_a_id == family_b_id:
        return True

    def family_document(family_id: str) -> Dict[str, Any] | None:
        if ObjectId.is_valid(family_id):
            found = db.families.find_one({"_id": ObjectId(family_id)})
            if found:
                return found
        return db.families.find_one({"family_id": family_id})

    family_a = family_document(family_a_id) or {}
    family_b = family_document(family_b_id) or {}

    def household_id_for_family(family: Dict[str, Any]) -> str:
        direct = str(family.get("household_id") or "").strip()
        if direct:
            return direct
        project_id = str(family.get("project_id") or "").strip()
        if not project_id:
            return ""
        candidates: List[Any] = [project_id]
        if ObjectId.is_valid(project_id):
            candidates.append(ObjectId(project_id))
        household = db.households.find_one(
            {"project_id": {"$in": candidates}}
        )
        return str((household or {}).get("_id") or "").strip()

    household_a = household_id_for_family(family_a)
    household_b = household_id_for_family(family_b)
    if not household_a or not household_b:
        return False

    return (
        db.household_links.find_one(
            {
                "link_status": "approved",
                "$or": [
                    {
                        "source_household_id": household_a,
                        "target_household_id": household_b,
                    },
                    {
                        "source_household_id": household_b,
                        "target_household_id": household_a,
                    },
                ],
            }
        )
        is not None
    )
