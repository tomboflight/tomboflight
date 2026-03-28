from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
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
def get_household_links(current_user: dict[str, Any] = Depends(require_admin)):
    links = list_household_links()
    return [build_household_link_response(link) for link in links]


@router.post("/", response_model=HouseholdLinkResponse)
def create_household_link_route(
    payload: HouseholdLinkCreate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    link = create_household_link(payload)
    return build_household_link_response(link)
