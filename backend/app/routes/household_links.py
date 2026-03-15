from fastapi import APIRouter

from app.schemas.household_link import (
    HouseholdLinkCreate,
    HouseholdLinkResponse,
    build_household_link_response,
)
from app.services.household_link_service import (
    create_household_link,
    list_household_links,
)

router = APIRouter(prefix="/household-links", tags=["Household Links"])


@router.get("/", response_model=list[HouseholdLinkResponse])
def get_household_links():
    links = list_household_links()
    return [build_household_link_response(link) for link in links]


@router.post("/", response_model=HouseholdLinkResponse)
def create_household_link_route(payload: HouseholdLinkCreate):
    link = create_household_link(payload)
    return build_household_link_response(link)
