from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import INTERNAL_ADMIN_KEYS, get_current_user, require_admin
from app.schemas.intake_submission import (
    IntakeSubmissionCreate,
    IntakeSubmissionListItem,
    IntakeSubmissionResponse,
    IntakeSubmissionStatusUpdate,
)
from app.services.intake_submission_service import (
    create_intake_submission,
    get_by_id,
    get_latest_for_user,
    list_all,
    list_for_user,
    update_status,
)

router = APIRouter(prefix="/intake-submissions", tags=["Intake Submissions"])


def _current_user_id(current_user: dict) -> str:
    raw = current_user.get("id") or current_user.get("_id") or current_user.get("user_id")
    if raw is None:
        raise HTTPException(status_code=401, detail="Authenticated user id is missing.")
    return str(raw)


def _current_user_email(current_user: dict) -> str:
    raw = current_user.get("email")
    if not raw:
        raise HTTPException(status_code=401, detail="Authenticated user email is missing.")
    return str(raw).strip().lower()


def _actor_label(current_user: dict) -> str:
    return (
        str(current_user.get("email") or "").strip().lower()
        or str(current_user.get("full_name") or "").strip()
        or str(current_user.get("name") or "").strip()
        or str(current_user.get("id") or "").strip()
        or "system"
    )


def _is_admin(user: dict[str, Any]) -> bool:
    values = {
        str(user.get("role") or "").strip().lower(),
        str(user.get("access_tier") or "").strip().lower(),
        str(user.get("department_role") or "").strip().lower(),
    }
    return any(value in INTERNAL_ADMIN_KEYS for value in values if value)


@router.post(
    "",
    response_model=IntakeSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    payload: IntakeSubmissionCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        return create_intake_submission(
            user_id=_current_user_id(current_user),
            email=_current_user_email(current_user),
            payload=payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/my-latest", response_model=IntakeSubmissionResponse)
def my_latest_submission(current_user: dict = Depends(get_current_user)):
    result = get_latest_for_user(_current_user_id(current_user))
    if not result:
        raise HTTPException(status_code=404, detail="No intake submissions found.")
    return result


@router.get("/my-list", response_model=list[IntakeSubmissionListItem])
def my_submission_list(
    limit: int = Query(default=10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    return list_for_user(_current_user_id(current_user), limit=limit)


@router.get("/{submission_id}", response_model=IntakeSubmissionResponse)
def get_submission(
    submission_id: str,
    current_user: dict = Depends(get_current_user),
):
    result = get_by_id(submission_id)
    if not result:
        raise HTTPException(status_code=404, detail="Intake submission not found.")

    current_user_id = _current_user_id(current_user)

    if result["user_id"] != current_user_id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to access this intake submission.")

    return result


@router.get("/admin/list", response_model=list[IntakeSubmissionListItem])
def admin_list_submissions(
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    _admin_user: dict = Depends(require_admin),
):
    return list_all(limit=limit, status=status_filter)


@router.patch("/{submission_id}/status", response_model=IntakeSubmissionResponse)
def admin_update_submission_status(
    submission_id: str,
    payload: IntakeSubmissionStatusUpdate,
    admin_user: dict = Depends(require_admin),
):
    try:
        return update_status(
            submission_id=submission_id,
            new_status=payload.status,
            reviewed_by=_actor_label(admin_user),
            review_notes=payload.review_notes,
            approval_notes=payload.approval_notes,
            rejection_reason=payload.rejection_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc