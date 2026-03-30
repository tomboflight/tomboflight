from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PublicMetadataPayload(BaseModel):
    name: str
    description: str
    image: str
    external_url: str
    attributes: list[dict[str, Any]] = Field(default_factory=list)
    tol: dict[str, Any] = Field(default_factory=dict)


class PublicManifestResponse(BaseModel):
    id: str
    project_id: str
    mint_record_id: str
    version_number: int
    schema_version: str
    public_token_id: str
    metadata_uri: str
    poster_image_uri_public: str
    payload: PublicMetadataPayload | dict[str, Any]
    build_hash: str
    certificate_hash: str | None = None
    approval_status: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PublicTokenLandingResponse(BaseModel):
    public_token_id: str
    metadata_uri: str
    project_id: str
    version_number: int
    poster_image_uri_public: str
    approval_status: str
    payload: PublicMetadataPayload | dict[str, Any]
