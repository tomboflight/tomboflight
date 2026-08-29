from pydantic import BaseModel, Field


class CollectionStatus(BaseModel):
    name: str
    created: bool
    indexes_created: list[str]
    indexes_failed: list[str] = Field(default_factory=list)


class BootstrapResponse(BaseModel):
    message: str
    database_name: str
    collections: list[CollectionStatus]


class LegacyIndexDropResult(BaseModel):
    collection: str
    dropped: list[str]
    skipped: list[str]


class DropLegacyIndexesResponse(BaseModel):
    message: str
    database_name: str
    results: list[LegacyIndexDropResult]
    total_dropped: int


class ProjectMembersBackfillResponse(BaseModel):
    message: str
    scanned: int
    backfilled: int
    already_present: int
    skipped: int


class WorkspaceAnchorBackfillResponse(BaseModel):
    message: str
    scanned: int
    provisioned: int
    already_present: int
    skipped: int
