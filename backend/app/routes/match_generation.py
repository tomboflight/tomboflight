from typing import Optional

from fastapi import APIRouter, Query

from app.services.match_generator_service import preview_matches, scan_database_for_matches

router = APIRouter(prefix="/match-generation", tags=["Match Generation"])


@router.post("/scan")
def run_match_scan(family_id: Optional[str] = Query(default=None)):
    return scan_database_for_matches(family_id=family_id)


@router.get("/preview")
def preview_match_scan(
    family_id: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
):
    return preview_matches(family_id=family_id, limit=limit)