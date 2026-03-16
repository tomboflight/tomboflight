from pydantic import BaseModel


class CollectionStatus(BaseModel):
    name: str
    created: bool
    indexes_created: list[str]


class BootstrapResponse(BaseModel):
    message: str
    database_name: str
    collections: list[CollectionStatus]