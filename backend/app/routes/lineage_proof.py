from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_database
from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
    require_package_capability,
)
from app.services.lineage_proof_service import generate_lineage_proof
from app.services.workspace_access_service import family_is_visible_to_user

router = APIRouter(
    prefix="/lineage-proof",
    tags=["Lineage Proof"],
)


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


def _require_family_access(
    family_id: str,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )

    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="family_id is required.",
        )

    if not ObjectId.is_valid(family_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid family id.",
        )

    family = db["families"].find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found.",
        )

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
            detail="Not authorized to access this lineage proof.",
        )

    return family


@router.get("/")
def get_lineage_proof(
    family_id: str = Query(...),
    ancestor_id: str = Query(...),
    descendant_id: str = Query(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_package_capability(
        current_user,
        "can_build_family_tree",
        detail="Your active package does not include lineage proof access.",
    )
    _require_family_access(family_id, current_user)

    return generate_lineage_proof(
        family_id=family_id,
        ancestor_id=ancestor_id,
        descendant_id=descendant_id,
    )
