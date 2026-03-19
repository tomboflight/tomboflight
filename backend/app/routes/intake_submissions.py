from fastapi import APIRouter, Depends, Query

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


@router.post("/intake-submissions", response_model=IntakeSubmissionResponse, status_code=201)
def create_submission(payload: IntakeSubmissionCreate, user=Depends(get_current_user)):
    saved = create_intake_submission(
        user_id=str(user["id"]),
        email=str(user["email"]),
        payload=payload.model_dump(),
    )
    return saved


@router.get("/intake-submissions/my-latest", response_model=IntakeSubmissionResponse)
def my_latest(user=Depends(get_current_user)):
    doc = get_latest_for_user(str(user["id"]))
    if not doc:
        # FastAPI will 404 if we raise; but your frontend expects a failure -> fallback is fine.
        # We'll return a clear empty error by raising.
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No intake submissions found.")
    return doc


@router.get("/intake-submissions/my-list", response_model=list[IntakeSubmissionListItem])
def my_list(
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
):
    return list_for_user(str(user["id"]), limit=limit)