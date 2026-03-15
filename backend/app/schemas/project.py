from datetime import datetime, UTC
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=150)
    family_id: str = Field(..., min_length=1)
    package_type: str = Field(..., min_length=1, max_length=100)
    status: str = "draft"


class ProjectResponse(BaseModel):
    id: str
    project_name: str
    family_id: str
    package_type: str
    status: str
    created_at: str


def build_project_response(data: dict) -> ProjectResponse:
    return ProjectResponse(
        id=str(data.get("_id", "")),
        project_name=data["project_name"],
        family_id=data["family_id"],
        package_type=data["package_type"],
        status=data.get("status", "draft"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
