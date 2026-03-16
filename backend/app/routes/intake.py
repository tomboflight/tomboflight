from fastapi import APIRouter

from app.schemas.intake import IntakeCreate, IntakeResponse, build_intake_response
from app.services.intake_service import (
    create_intake_submission,
    list_intake_submissions,
)

router = APIRouter(prefix="/intake", tags=["Intake"])


@router.get("/", response_model=list[IntakeResponse])
def get_intake_submissions():
    submissions = list_intake_submissions()
    return [build_intake_response(item) for item in submissions]


@router.post("/request-access", response_model=IntakeResponse)
def request_access(payload: IntakeCreate):
    submission = create_intake_submission(payload)
    return build_intake_response(submission)
