from datetime import UTC, datetime
from pydantic import BaseModel, Field

from app.core.state_catalog import normalize_relationship_link_state


class IdentityLinkCreate(BaseModel):
    family_member_id: str = Field(..., min_length=1)
    canonical_person_id: str = Field(..., min_length=1)
    link_status: str = Field(default="linked", min_length=1, max_length=50)
    linked_by: str = Field(..., min_length=1)
    notes: str | None = None


class IdentityLinkResponse(BaseModel):
    id: str
    family_member_id: str
    canonical_person_id: str
    link_status: str
    linked_by: str
    notes: str | None = None
    created_at: str


def build_identity_link_response(data: dict) -> IdentityLinkResponse:
    return IdentityLinkResponse(
        id=str(data.get("_id", "")),
        family_member_id=data["family_member_id"],
        canonical_person_id=data["canonical_person_id"],
        link_status=normalize_relationship_link_state(
            data.get("status") or data.get("link_status"),
            default="active",
        ),
        linked_by=data["linked_by"],
        notes=data.get("notes"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
