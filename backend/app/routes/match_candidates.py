from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.metadata import apply_update_metadata
from app.database import get_database
from app.dependencies.auth import get_current_user, require_admin
from app.services.approval import ApprovalError, approve_match_candidate
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/match-candidates", tags=["match_candidates"])


@router.get("")
def list_match_candidates(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    results = []

    for item in db.match_candidates.find().sort("created_at", -1):
        item["_id"] = str(item["_id"])
        results.append(item)

    return results


@router.post("/{candidate_id}/approve")
def approve_candidate(candidate_id: str, current_user: dict = Depends(require_admin)):
    user_id = str(current_user.get("_id")) if current_user.get("_id") else None

    try:
        result = approve_match_candidate(candidate_id=candidate_id, actor_user_id=user_id)
        return result
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{candidate_id}/reject")
def reject_candidate(candidate_id: str, notes: dict | None = None, current_user: dict = Depends(require_admin)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(candidate_id):
        raise HTTPException(status_code=400, detail="Invalid candidate id.")

    candidate = db.match_candidates.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        raise HTTPException(status_code=404, detail="Match candidate not found.")

    if candidate.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending match candidates can be rejected.")

    user_id = str(current_user.get("_id")) if current_user.get("_id") else None

    update_data = {
        "status": "rejected",
        "rejected_by": user_id,
        "review_notes": (notes or {}).get("review_notes", ""),
    }
    update_data = apply_update_metadata(update_data, user_id)

    db.match_candidates.update_one(
        {"_id": ObjectId(candidate_id)},
        {"$set": update_data},
    )

    create_audit_log(
        action="match_candidate_rejected",
        actor_user_id=user_id,
        entity_type="match_candidate",
        entity_id=candidate_id,
        details={"review_notes": update_data.get("review_notes", "")},
    )

    return {"message": "Match candidate rejected successfully."}