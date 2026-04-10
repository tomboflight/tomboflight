from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_database
from app.dependencies.auth import require_permission
from app.services.match_generator_service import preview_matches, scan_database_for_matches

router = APIRouter(prefix="/match-generation", tags=["Match Generation"])


def _validate_family_id_if_present(family_id: Optional[str]) -> None:
    if family_id is None:
        return

    if not ObjectId.is_valid(family_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid family id.",
        )

    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )

    family = db["families"].find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found.",
        )


@router.post("/scan")
def run_match_scan(
    family_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(require_permission("admin.access")),
):
    _validate_family_id_if_present(family_id)
    return scan_database_for_matches(family_id=family_id)


@router.get("/preview")
def preview_match_scan(
    family_id: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: dict = Depends(require_permission("admin.access")),
):
    _validate_family_id_if_present(family_id)
    return preview_matches(family_id=family_id, limit=limit)