from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.intake_submission import (
    IntakeSubmissionCreate,
    IntakeSubmissionDetailResponse,
    IntakeSubmissionResponse,
)
from app.services.intake_submission_service import (
    create_intake_submission,
    get_intake_submission_by_id_for_user,
    get_latest_intake_submission_for_user,
)

router = APIRouter(prefix="/intake-submissions", tags=["Intake Submissions"])


@router.post(
    "",
    response_model=IntakeSubmissionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_intake(
    payload: IntakeSubmissionCreate,
    current_user: dict = Depends(get_current_user),
):
    if not payload.review.confirm_accuracy:
        raise HTTPException(
            status_code=400,
            detail="You must confirm intake accuracy before submission.",
        )

    try:
        record = create_intake_submission(
            current_user=current_user,
            payload=payload.model_dump(),
        )
        return record
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/my-latest",
    response_model=IntakeSubmissionDetailResponse,
)
def get_my_latest_intake(
    current_user: dict = Depends(get_current_user),
):
    try:
        record = get_latest_intake_submission_for_user(str(current_user["_id"]))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(status_code=404, detail="No intake submission found.")

    return record


@router.get(
    "/{submission_id}",
    response_model=IntakeSubmissionDetailResponse,
)
def get_my_intake_by_id(
    submission_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        record = get_intake_submission_by_id_for_user(
            submission_id=submission_id,
            user_id=str(current_user["_id"]),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(status_code=404, detail="Intake submission not found.")

    return record