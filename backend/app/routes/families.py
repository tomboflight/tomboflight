from fastapi import APIRouter

from app.schemas.family import FamilyCreate, FamilyResponse, build_family_response
from app.services.family_service import create_family, list_families

router = APIRouter(prefix="/families", tags=["Families"])


@router.get("/", response_model=list[FamilyResponse])
def get_families():
    families = list_families()
    return [build_family_response(family) for family in families]


@router.post("/", response_model=FamilyResponse)
def create_family_route(payload: FamilyCreate):
    family = create_family(payload)
    return build_family_response(family)
