from fastapi import APIRouter

from app.services.identity_anchor_service import (
    create_identity_anchor,
    get_identity_anchor,
)

router = APIRouter(
    prefix="/identity-anchor",
    tags=["Identity Anchor"],
)


@router.post("/create")
def create_anchor(person_id: str, family_id: str):
    return create_identity_anchor(person_id, family_id)


@router.get("/{person_id}")
def fetch_anchor(person_id: str):
    return get_identity_anchor(person_id)