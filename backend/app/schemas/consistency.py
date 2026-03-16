from pydantic import BaseModel


class ConsistencyIssue(BaseModel):
    type: str
    severity: str
    description: str
    entity_id: str | None = None


class ConsistencyReport(BaseModel):
    issue_count: int
    issues: list[ConsistencyIssue]