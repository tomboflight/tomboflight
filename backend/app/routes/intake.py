from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.intake import IntakeCreate
from app.services.intake_submission_service import (
    create_intake_submission,
    get_latest_for_user,
    list_for_user,
)

router = APIRouter(prefix="/intake", tags=["Intake"])


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


@router.get("/")
def get_intake_submissions(current_user: dict[str, Any] = Depends(get_current_user)):
    """
    Backward-compatible intake listing route.
    Returns only the current user's intake submissions.
    """
    return list_for_user(_current_user_id(current_user), limit=50)


@router.get("/latest")
def get_latest_intake_submission(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Backward-compatible latest intake route.
    """
    doc = get_latest_for_user(_current_user_id(current_user))
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No intake submissions found.",
        )
    return doc


@router.post("/request-access", status_code=status.HTTP_201_CREATED)
def request_access(
    payload: IntakeCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Backward-compatible access request route.
    Stores old intake request data inside the newer intake_submissions structure.
    """
    package_interest = str(payload.package_interest).strip() or "Legacy Access Request"
    package_slug = package_interest.lower().replace(" ", "-")
    contact_email = str(payload.email).strip().lower()
    submitted_at = datetime.now(UTC).isoformat()

    compatibility_payload = {
        "package_name": package_interest,
        "package_slug": package_slug,
        "status": "submitted",
        "source": "legacy-intake-route",
        "submitted_at": submitted_at,
        "household": {
            "household_name": f"{payload.full_name.strip()} Household",
            "primary_contact_name": payload.full_name,
            "primary_contact_email": contact_email,
            "project_scope": payload.family_goal,
        },
        "family_map": {
            "family_branch_name": f"{payload.full_name.strip()} Family",
            "family_structure_summary": payload.family_goal,
        },
        "uploads": {
            "primary_asset_type": "",
            "uploads_rights_confirmed": True,
            "uploads_minimization_confirmed": True,
        },
        "consent": {
            "consent_process": True,
            "consent_store": True,
            "consent_authority": True,
            "consent_review_disclaimer": True,
            "visibility_preference": "private",
        },
        "review": {
            "confirm_accuracy": True,
            "final_intake_notes": payload.family_goal,
        },
        "legacy_request": payload.model_dump(),
    }

    saved = create_intake_submission(
        user_id=_current_user_id(current_user),
        email=_current_user_email(current_user),
        payload=compatibility_payload,
    )
    return saved
