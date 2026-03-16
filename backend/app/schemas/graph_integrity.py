from pydantic import BaseModel


class GraphIssue(BaseModel):
    issue_type: str
    message: str
    record: dict


class GraphIntegrityResponse(BaseModel):
    family_id: str
    family_name: str | None = None
    member_count: int
    relationship_count: int
    isolated_member_ids: list[str]
    issues: list[GraphIssue]
    is_healthy: bool