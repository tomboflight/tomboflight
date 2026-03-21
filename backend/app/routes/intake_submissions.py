from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.schemas.intake_submission import (
    IntakeSubmissionCreate,
    IntakeSubmissionListItem,
    IntakeSubmissionResponse,
)
from app.services.intake_submission_service import (
    create_intake_submission,
    get_latest_for_user,
    list_for_user,
)

router = APIRouter(prefix="", tags=["Intake Submissions"])


def _current_user_id(user: dict) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_email(user: dict) -> str:
    raw_email = user.get("email")
    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user email is missing.",
        )
    return str(raw_email)


@router.post(
    "/intake-submissions",
    response_model=IntakeSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    payload: IntakeSubmissionCreate,
    user: dict = Depends(get_current_user),
) -> IntakeSubmissionResponse:
    saved = create_intake_submission(
        user_id=_current_user_id(user),
        email=_current_user_email(user),
        payload=payload.model_dump(),
    )
    return saved


@router.get(
    "/intake-submissions/my-latest",
    response_model=IntakeSubmissionResponse,
)
def my_latest(user: dict = Depends(get_current_user)) -> IntakeSubmissionResponse:
    doc = get_latest_for_user(_current_user_id(user))
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No intake submissions found.",
        )
    return doc


@router.get(
    "/intake-submissions/my-list",
    response_model=list[IntakeSubmissionListItem],
)
def my_list(
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
) -> list[IntakeSubmissionListItem]:
    return list_for_user(_current_user_id(user), limit=limit)
