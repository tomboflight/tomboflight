from fastapi import APIRouter

from app.schemas.household import (
    HouseholdCreate,
    HouseholdResponse,
    build_household_response,
)
from app.services.household_service import create_household, list_households

router = APIRouter(prefix="/households", tags=["Households"])


@router.get("/", response_model=list[HouseholdResponse])
def get_households():
    households = list_households()
    return [build_household_response(household) for household in households]


@router.post("/", response_model=HouseholdResponse)
def create_household_route(payload: HouseholdCreate):
    household = create_household(payload)
    return build_household_response(household)
