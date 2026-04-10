from pydantic import BaseModel


class CollectionStatus(BaseModel):
    name: str
    created: bool
    indexes_created: list[str]


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