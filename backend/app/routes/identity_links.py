from fastapi import APIRouter

from app.schemas.identity_link import (
    IdentityLinkCreate,
    IdentityLinkResponse,
    build_identity_link_response,
)
from app.services.identity_link_service import (
    create_identity_link,
    list_identity_links,
)

router = APIRouter(prefix="/identity-links", tags=["Identity Links"])


@router.get("/", response_model=list[IdentityLinkResponse])
def get_identity_links():
    links = list_identity_links()
    return [build_identity_link_response(link) for link in links]


@router.post("/", response_model=IdentityLinkResponse)
def create_identity_link_route(payload: IdentityLinkCreate):
    link = create_identity_link(payload)
    return build_identity_link_response(link)