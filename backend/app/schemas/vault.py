from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


VaultScope = Literal["personal", "household", "linked_family", "memorial"]
VaultPrivacy = Literal["private_owner", "selected_relatives", "household_admins", "all_linked", "public_memorial"]
VaultPermissionRole = Literal["owner", "steward", "editor", "viewer", "executor"]
VaultItemType = Literal["photo", "document", "audio", "video", "note", "heirloom_record", "letter", "certificate", "other"]


class VaultItemCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    item_type: VaultItemType = Field(default="other")
    vault_scope: VaultScope = Field(default="personal")
    privacy: VaultPrivacy = Field(default="private_owner")
    collection_id: Optional[str] = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VaultItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    vault_scope: Optional[VaultScope] = None
    privacy: Optional[VaultPrivacy] = None
    collection_id: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class VaultCollectionCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    vault_scope: VaultScope = Field(default="personal")
    privacy: VaultPrivacy = Field(default="private_owner")


class VaultAccessGrantCreate(BaseModel):
    vault_item_id: str = Field(..., min_length=1)
    grantee_user_id: Optional[str] = None
    grantee_project_id: Optional[str] = None
    permission_role: VaultPermissionRole = Field(default="viewer")
    expires_at: Optional[datetime] = None


class VaultReleaseRuleCreate(BaseModel):
    vault_item_id: str = Field(..., min_length=1)
    trigger_type: Literal["on_death", "on_date", "on_age_milestone", "after_trustee_approval", "to_descendants", "to_spouse", "to_named"] = Field(...)
    trigger_value: Optional[str] = Field(default=None, max_length=200)
    release_to: Literal["descendants", "spouse", "named_list", "household", "all_linked", "public"] = Field(default="descendants")
    named_recipients: list[str] = Field(default_factory=list)
    trustee_user_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
