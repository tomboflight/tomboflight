from fastapi import APIRouter

from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipResponse,
    build_relationship_response,
)
from app.services.relationship_service import (
    create_relationship,
    list_relationships,
)

router = APIRouter(prefix="/relationships", tags=["Relationships"])


@router.get("/", response_model=list[RelationshipResponse])
def get_relationships():
    relationships = list_relationships()
    return [build_relationship_response(item) for item in relationships]


@router.post("/", response_model=RelationshipResponse)
def create_relationship_route(payload: RelationshipCreate):
    relationship = create_relationship(payload)
    return build_relationship_response(relationship)
