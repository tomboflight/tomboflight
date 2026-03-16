from fastapi import APIRouter

from app.schemas.verification_record import (
    VerificationRecordCreate,
    VerificationRecordResponse,
    build_verification_record_response,
)
from app.services.verification_record_service import (
    create_verification_record,
    list_verification_records,
)

router = APIRouter(prefix="/verification-records", tags=["Verification Records"])


@router.get("/", response_model=list[VerificationRecordResponse])
def get_verification_records():
    records = list_verification_records()
    return [build_verification_record_response(record) for record in records]


@router.post("/", response_model=VerificationRecordResponse)
def create_verification_record_route(payload: VerificationRecordCreate):
    record = create_verification_record(payload)
    return build_verification_record_response(record)