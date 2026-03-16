from fastapi import APIRouter

from app.schemas.narrative_record import (
    NarrativeRecordCreate,
    NarrativeRecordResponse,
    build_narrative_record_response,
)
from app.services.narrative_record_service import (
    create_narrative_record,
    list_narrative_records,
)

router = APIRouter(prefix="/narrative-records", tags=["Narrative Records"])


@router.get("/", response_model=list[NarrativeRecordResponse])
def get_narrative_records():
    records = list_narrative_records()
    return [build_narrative_record_response(record) for record in records]


@router.post("/", response_model=NarrativeRecordResponse)
def create_narrative_record_route(payload: NarrativeRecordCreate):
    record = create_narrative_record(payload)
    return build_narrative_record_response(record)