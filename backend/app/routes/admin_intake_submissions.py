from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies.auth import require_admin
from app.schemas.intake_submission import (
    IntakeSubmissionListItem,
    IntakeSubmissionResponse,
    IntakeSubmissionStatusUpdate,
)
from app.services.intake_pipeline_service import provision_build_from_submission
from app.services.intake_submission_service import (
    get_by_id,
    list_all,
    update_status,
)

router = APIRouter(
    prefix="/admin/intake-submissions",
    tags=["Admin Intake Submissions"],
)


class IntakeAdminNotesPayload(BaseModel):
    review_notes: str = Field(default="")
    approval_notes: str = Field(default="")
    rejection_reason: str = Field(default="")


class IntakeProvisionBuildPayload(BaseModel):
    family_name_override: str = Field(default="")
    project_name_override: str = Field(default="")
    production_notes: str = Field(default="")


def _reviewed_by(current_admin: dict[str, Any]) -> str:
    return str(
        current_admin.get("email")
        or current_admin.get("full_name")
        or current_admin.get("name")
        or current_admin.get("id")
        or "admin"
    ).strip()


@router.get("/", response_model=list[IntakeSubmissionListItem])
def list_admin_intake_submissions(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    current_admin: dict[str, Any] = Depends(require_admin),
):
    return list_all(limit=limit, status=status_filter)


@router.get("/{submission_id}", response_model=IntakeSubmissionResponse)
def get_admin_intake_submission(
    submission_id: str,
    current_admin: dict[str, Any] = Depends(require_admin),
):
    submission = get_by_id(submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intake submission not found.",
        )
    return submission


@router.post("/{submission_id}/status", response_model=IntakeSubmissionResponse)
def set_admin_intake_submission_status(
    submission_id: str,
    payload: IntakeSubmissionStatusUpdate,
    current_admin: dict[str, Any] = Depends(require_admin),
):
    try:
        return update_status(
            submission_id=submission_id,
            new_status=payload.status,
            reviewed_by=_reviewed_by(current_admin),
            review_notes=payload.review_notes,
            approval_notes=payload.approval_notes,
            rejection_reason=payload.rejection_reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{submission_id}/in-review", response_model=IntakeSubmissionResponse)
def mark_admin_intake_in_review(
    submission_id: str,
    payload: IntakeAdminNotesPayload,
    current_admin: dict[str, Any] = Depends(require_admin),
):
    try:
        return update_status(
            submission_id=submission_id,
            new_status="in_review",
            reviewed_by=_reviewed_by(current_admin),
            review_notes=payload.review_notes,
            approval_notes=payload.approval_notes,
            rejection_reason=payload.rejection_reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{submission_id}/approve", response_model=IntakeSubmissionResponse)
def approve_admin_intake_submission(
    submission_id: str,
    payload: IntakeAdminNotesPayload,
    current_admin: dict[str, Any] = Depends(require_admin),
):
    try:
        return update_status(
            submission_id=submission_id,
            new_status="approved",
            reviewed_by=_reviewed_by(current_admin),
            review_notes=payload.review_notes,
            approval_notes=payload.approval_notes,
            rejection_reason="",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{submission_id}/reject", response_model=IntakeSubmissionResponse)
def reject_admin_intake_submission(
    submission_id: str,
    payload: IntakeAdminNotesPayload,
    current_admin: dict[str, Any] = Depends(require_admin),
):
    try:
        return update_status(
            submission_id=submission_id,
            new_status="rejected",
            reviewed_by=_reviewed_by(current_admin),
            review_notes=payload.review_notes,
            approval_notes="",
            rejection_reason=payload.rejection_reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{submission_id}/provision-build", response_model=IntakeSubmissionResponse)
def provision_admin_intake_build(
    submission_id: str,
    payload: IntakeProvisionBuildPayload,
    current_admin: dict[str, Any] = Depends(require_admin),
):
    try:
        return provision_build_from_submission(
            submission_id=submission_id,
            provisioned_by=_reviewed_by(current_admin),
            family_name_override=payload.family_name_override,
            project_name_override=payload.project_name_override,
            production_notes=payload.production_notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc