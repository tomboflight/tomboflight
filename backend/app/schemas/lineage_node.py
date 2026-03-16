from datetime import datetime, UTC
from pydantic import BaseModel, Field


class LineageNodeCreate(BaseModel):
    family_id: str = Field(..., min_length=1)
    member_id: str = Field(..., min_length=1)
    generation: int = Field(..., ge=0)
    x: float = 0
    y: float = 0
    parent_node_ids: list[str] = []
    child_node_ids: list[str] = []


class LineageNodeResponse(BaseModel):
    id: str
    family_id: str
    member_id: str
    generation: int
    x: float
    y: float
    parent_node_ids: list[str]
    child_node_ids: list[str]
    created_at: str


def build_lineage_node_response(data: dict) -> LineageNodeResponse:
    return LineageNodeResponse(
        id=str(data.get("_id", "")),
        family_id=data["family_id"],
        member_id=data["member_id"],
        generation=data["generation"],
        x=data.get("x", 0),
        y=data.get("y", 0),
        parent_node_ids=data.get("parent_node_ids", []),
        child_node_ids=data.get("child_node_ids", []),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
