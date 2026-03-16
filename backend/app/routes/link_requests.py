from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas.link_request import (
    LinkRequestCreate,
    LinkRequestResponse,
    build_link_request_response,
)
from app.services.link_request_service import (
    approve_link_request,
    create_link_request,
    list_link_requests,
    reject_link_request,
)

router = APIRouter(prefix="/link-requests", tags=["Link Requests"])


class LinkRequestDecision(BaseModel):
    decided_by: str = Field(..., min_length=1, max_length=150)


@router.get("/", response_model=list[LinkRequestResponse])
def get_link_requests():
    requests = list_link_requests()
    return [build_link_request_response(item) for item in requests]


@router.post("/", response_model=LinkRequestResponse)
def create_link_request_route(payload: LinkRequestCreate):
    request = create_link_request(payload)
    return build_link_request_response(request)


@router.post("/{request_id}/approve", response_model=LinkRequestResponse)
def approve_link_request_route(request_id: str, payload: LinkRequestDecision):
    updated_request = approve_link_request(request_id, payload.decided_by)

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)


@router.post("/{request_id}/reject", response_model=LinkRequestResponse)
def reject_link_request_route(request_id: str, payload: LinkRequestDecision):
    updated_request = reject_link_request(request_id, payload.decided_by)

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)