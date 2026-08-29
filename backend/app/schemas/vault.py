from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


VaultScope = Literal["personal", "household", "linked_family", "memorial", "organization"]
VaultPrivacy = Literal[
    "private_owner",
    "owner_and_co_owner",
    "selected_relatives",
    "household_admins",
    "all_linked",
    "public_memorial",
]
VaultPermissionRole = Literal["owner", "steward", "editor", "viewer", "executor"]
VaultItemType = Literal["photo", "document", "audio", "video", "note", "heirloom_record", "letter", "certificate", "other"]
VaultReleaseState = Literal["draft", "scheduled", "released"]
VaultGrantStatus = Literal["active", "revoked"]
VaultReleaseRuleStatus = Literal["active", "satisfied", "revoked"]
VaultReleaseTrigger = Literal[
    "on_death",
    "on_date",
    "on_age_milestone",
    "after_trustee_approval",
    "to_descendants",
    "to_spouse",
    "to_named",
]
VaultReleaseAudience = Literal[
    "descendants",
    "spouse",
    "named_list",
    "household",
    "all_linked",
    "public",
]


class VaultItemCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    family_id: Optional[str] = Field(default=None)
    member_id: Optional[str] = Field(default=None)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    item_type: VaultItemType = Field(default="other")
    vault_scope: VaultScope = Field(default="personal")
    privacy: VaultPrivacy = Field(default="private_owner")
    release_state: VaultReleaseState = Field(default="draft")
    reveal_at: Optional[datetime] = Field(default=None)
    collection_id: Optional[str] = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    upload_id: Optional[str] = Field(default=None, min_length=1)
    current_upload_id: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_release_and_upload(self) -> "VaultItemCreate":
        if self.release_state == "scheduled" and self.reveal_at is None:
            raise ValueError("Scheduled vault items require reveal_at.")
        if self.upload_id and self.current_upload_id and self.upload_id != self.current_upload_id:
            raise ValueError("upload_id and current_upload_id must identify the same initial upload.")
        if self.vault_scope == "organization" and (self.family_id or self.member_id):
            raise ValueError("Organization vault items cannot reference a family or family member.")
        return self


class VaultItemUpdate(BaseModel):
    family_id: Optional[str] = None
    member_id: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    vault_scope: Optional[VaultScope] = None
    privacy: Optional[VaultPrivacy] = None
    release_state: Optional[VaultReleaseState] = None
    reveal_at: Optional[datetime] = None
    collection_id: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_release(self) -> "VaultItemUpdate":
        if (
            self.release_state == "scheduled"
            and "reveal_at" in self.model_fields_set
            and self.reveal_at is None
        ):
            raise ValueError("Scheduled vault items require reveal_at.")
        return self


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

    @model_validator(mode="after")
    def validate_grantee(self) -> "VaultAccessGrantCreate":
        if not (str(self.grantee_user_id or "").strip() or str(self.grantee_project_id or "").strip()):
            raise ValueError("A grantee_user_id or grantee_project_id is required.")
        if self.permission_role == "owner":
            raise ValueError("Ownership cannot be assigned through a vault access grant.")
        return self


class VaultAccessGrantUpdate(BaseModel):
    permission_role: Optional[VaultPermissionRole] = None
    expires_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_role(self) -> "VaultAccessGrantUpdate":
        if self.permission_role == "owner":
            raise ValueError("Ownership cannot be assigned through a vault access grant.")
        if not self.model_fields_set:
            raise ValueError("At least one grant field must be supplied.")
        return self


class VaultReleaseRuleCreate(BaseModel):
    vault_item_id: str = Field(..., min_length=1)
    trigger_type: VaultReleaseTrigger = Field(...)
    trigger_value: Optional[str] = Field(default=None, max_length=200)
    release_to: VaultReleaseAudience = Field(default="descendants")
    named_recipients: list[str] = Field(default_factory=list)
    trustee_user_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_rule(self) -> "VaultReleaseRuleCreate":
        _validate_release_rule_fields(
            trigger_type=self.trigger_type,
            trigger_value=self.trigger_value,
            release_to=self.release_to,
            named_recipients=self.named_recipients,
            trustee_user_id=self.trustee_user_id,
        )
        return self


class VaultReleaseRuleUpdate(BaseModel):
    trigger_type: Optional[VaultReleaseTrigger] = None
    trigger_value: Optional[str] = Field(default=None, max_length=200)
    release_to: Optional[VaultReleaseAudience] = None
    named_recipients: Optional[list[str]] = None
    trustee_user_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[Literal["active", "satisfied"]] = None

    @model_validator(mode="after")
    def validate_update(self) -> "VaultReleaseRuleUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one release-rule field must be supplied.")
        return self


def _validate_release_rule_fields(
    *,
    trigger_type: VaultReleaseTrigger,
    trigger_value: Optional[str],
    release_to: VaultReleaseAudience,
    named_recipients: list[str],
    trustee_user_id: Optional[str],
) -> None:
    normalized_value = str(trigger_value or "").strip()
    recipients = [str(value).strip() for value in named_recipients if str(value).strip()]
    if trigger_type == "on_date":
        if not normalized_value:
            raise ValueError("on_date release rules require trigger_value.")
        try:
            datetime.fromisoformat(normalized_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("on_date trigger_value must be an ISO-8601 date or datetime.") from exc
    if trigger_type == "on_age_milestone":
        try:
            age = int(normalized_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("on_age_milestone trigger_value must be an age.") from exc
        if age < 1 or age > 150:
            raise ValueError("on_age_milestone trigger_value must be between 1 and 150.")
    if trigger_type != "on_date" and not str(trustee_user_id or "").strip():
        raise ValueError("Non-date release rules require trustee_user_id for governed verification.")
    if (trigger_type == "to_named" or release_to == "named_list") and not recipients:
        raise ValueError("Named release rules require at least one named recipient.")
