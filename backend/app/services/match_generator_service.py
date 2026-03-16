from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any, Dict, List, Optional

from app.database import get_database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def name_similarity(name1: str, name2: str) -> float:
    if not name1 or not name2:
        return 0.0
    return SequenceMatcher(None, normalize(name1), normalize(name2)).ratio()


def exact_match_score(value1: Optional[str], value2: Optional[str], weight: float) -> float:
    if not value1 or not value2:
        return 0.0
    return weight if normalize(value1) == normalize(value2) else 0.0


def partial_similarity_score(value1: Optional[str], value2: Optional[str], weight: float) -> float:
    if not value1 or not value2:
        return 0.0
    similarity = SequenceMatcher(None, normalize(value1), normalize(value2)).ratio()
    return similarity * weight


def build_full_name(member: Dict[str, Any]) -> str:
    first_name = member.get("first_name", "") or ""
    middle_name = member.get("middle_name", "") or ""
    last_name = member.get("last_name", "") or ""
    return " ".join(part for part in [first_name, middle_name, last_name] if part).strip()


def get_member_display_data(member: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(member.get("_id")),
        "family_id": str(member.get("family_id", "")),
        "first_name": member.get("first_name"),
        "middle_name": member.get("middle_name"),
        "last_name": member.get("last_name"),
        "full_name": build_full_name(member),
        "birth_date": member.get("birth_date"),
        "gender": member.get("gender"),
        "birth_place": member.get("birth_place"),
        "mother_name": member.get("mother_name"),
        "father_name": member.get("father_name"),
    }


def score_pair(member1: Dict[str, Any], member2: Dict[str, Any]) -> Dict[str, Any]:
    full_name_1 = build_full_name(member1)
    full_name_2 = build_full_name(member2)

    score = 0.0
    reasons: List[str] = []

    name_score = name_similarity(full_name_1, full_name_2) * 50
    score += name_score
    if name_score >= 35:
        reasons.append("strong_name_match")
    elif name_score >= 20:
        reasons.append("partial_name_match")

    birth_date_score = exact_match_score(member1.get("birth_date"), member2.get("birth_date"), 20)
    score += birth_date_score
    if birth_date_score:
        reasons.append("birth_date_match")

    gender_score = exact_match_score(member1.get("gender"), member2.get("gender"), 5)
    score += gender_score
    if gender_score:
        reasons.append("gender_match")

    birth_place_score = partial_similarity_score(
        member1.get("birth_place"),
        member2.get("birth_place"),
        10,
    )
    score += birth_place_score
    if birth_place_score >= 7:
        reasons.append("birth_place_similarity")

    mother_score = partial_similarity_score(
        member1.get("mother_name"),
        member2.get("mother_name"),
        7.5,
    )
    score += mother_score
    if mother_score >= 5:
        reasons.append("mother_name_similarity")

    father_score = partial_similarity_score(
        member1.get("father_name"),
        member2.get("father_name"),
        7.5,
    )
    score += father_score
    if father_score >= 5:
        reasons.append("father_name_similarity")

    score = round(min(score, 100.0), 2)

    if score >= 85:
        confidence = "high"
    elif score >= 65:
        confidence = "medium"
    elif score >= 50:
        confidence = "low"
    else:
        confidence = "ignore"

    return {
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
    }


def candidate_exists(member1_id: str, member2_id: str) -> bool:
    db = get_database()
    if db is None:
        return False

    existing = db.match_candidates.find_one(
        {
            "$or": [
                {"member_1_id": member1_id, "member_2_id": member2_id},
                {"member_1_id": member2_id, "member_2_id": member1_id},
            ]
        }
    )
    return existing is not None


def generate_match_candidate(member1: Dict[str, Any], member2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    member1_data = get_member_display_data(member1)
    member2_data = get_member_display_data(member2)

    if member1_data["id"] == member2_data["id"]:
        return None

    if candidate_exists(member1_data["id"], member2_data["id"]):
        return None

    scoring = score_pair(member1, member2)

    if scoring["confidence"] == "ignore":
        return None

    now = utc_now()

    return {
        "member_1_id": member1_data["id"],
        "member_2_id": member2_data["id"],
        "member_1": member1_data,
        "member_2": member2_data,
        "score": scoring["score"],
        "confidence": scoring["confidence"],
        "reasons": scoring["reasons"],
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "approved_by": None,
        "approved_at": None,
        "canonical_person_id": None,
    }


def scan_database_for_matches(family_id: Optional[str] = None) -> Dict[str, Any]:
    db = get_database()
    if db is None:
        return {
            "success": False,
            "error": "Database connection is not available.",
        }

    query: Dict[str, Any] = {}

    if family_id:
        query["family_id"] = family_id

    members = list(db.family_members.find(query))

    scanned_pairs = 0
    created_candidates = 0
    skipped_existing = 0
    ignored_pairs = 0
    inserted_ids: List[str] = []

    for member1, member2 in combinations(members, 2):
        scanned_pairs += 1

        member1_id = str(member1.get("_id"))
        member2_id = str(member2.get("_id"))

        if candidate_exists(member1_id, member2_id):
            skipped_existing += 1
            continue

        candidate = generate_match_candidate(member1, member2)

        if not candidate:
            ignored_pairs += 1
            continue

        result = db.match_candidates.insert_one(candidate)
        inserted_ids.append(str(result.inserted_id))
        created_candidates += 1

    return {
        "success": True,
        "family_id": family_id,
        "members_scanned": len(members),
        "pairs_scanned": scanned_pairs,
        "candidates_created": created_candidates,
        "existing_candidates_skipped": skipped_existing,
        "ignored_pairs": ignored_pairs,
        "inserted_candidate_ids": inserted_ids,
    }


def preview_matches(family_id: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
    db = get_database()
    if db is None:
        return {
            "success": False,
            "error": "Database connection is not available.",
            "matches": [],
        }

    query: Dict[str, Any] = {}

    if family_id:
        query["family_id"] = family_id

    members = list(db.family_members.find(query))
    previews: List[Dict[str, Any]] = []

    for member1, member2 in combinations(members, 2):
        candidate = generate_match_candidate(member1, member2)
        if candidate:
            previews.append(candidate)

    previews.sort(key=lambda item: item["score"], reverse=True)

    return {
        "success": True,
        "family_id": family_id,
        "total_preview_matches": len(previews),
        "matches": previews[:limit],
    }