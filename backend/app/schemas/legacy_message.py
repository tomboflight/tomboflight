from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MessageType = Literal[
    "letter",
    "time_capsule",
    "open_when",
    "family_principle",
    "voice_note",
    "memory_prompt",
    "lineage_milestone",
    "heirloom_assignment",
    "legacy_handoff",
    "descendant_story_branch",
]
ReleaseTrigger = Literal[
    "on_death",
    "on_date",
    "on_age_milestone",
    "open_when",
    "immediate",
    "manual",
]
RecipientScope = Literal[
    "descendants",
    "spouse",
    "named_list",
    "household",
    "all_linked",
    "public",
]


def _normalize_named_recipients(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        recipient_id = str(value or "").strip()
        if not recipient_id:
            raise ValueError("named_recipients cannot contain blank user ids.")
        if recipient_id not in normalized:
            normalized.append(recipient_id)
    return normalized


def _validate_release_value_shape(trigger: str, release_value: str | None) -> None:
    normalized_value = str(release_value or "").strip()
    if trigger == "on_date" and not normalized_value:
        raise ValueError("release_value is required for an on_date message.")
    if trigger == "on_age_milestone":
        if not normalized_value.isdigit() or not 1 <= int(normalized_value) <= 150:
            raise ValueError("release_value must be an age from 1 through 150.")
    if trigger == "open_when" and not normalized_value:
        raise ValueError("release_value is required for an open_when message.")
    if trigger in {"on_death", "immediate", "manual"} and normalized_value:
        raise ValueError(f"release_value is not allowed for a {trigger} message.")


class LegacyMessageCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=50000)
    message_type: MessageType = Field(default="letter")
    release_trigger: ReleaseTrigger = Field(default="manual")
    release_value: str | None = Field(default=None, max_length=500)
    recipient_scope: RecipientScope = Field(default="descendants")
    named_recipients: list[str] = Field(default_factory=list)
    branch_tag: str | None = Field(default=None, max_length=100)
    is_private: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("named_recipients")
    @classmethod
    def validate_named_recipients(cls, values: list[str]) -> list[str]:
        return _normalize_named_recipients(values)

    @model_validator(mode="after")
    def validate_release_and_recipient_configuration(self) -> LegacyMessageCreate:
        _validate_release_value_shape(self.release_trigger, self.release_value)
        if self.recipient_scope == "named_list" and not self.named_recipients:
            raise ValueError(
                "named_recipients is required when recipient_scope is named_list."
            )
        if self.recipient_scope != "named_list" and self.named_recipients:
            raise ValueError(
                "named_recipients is only allowed when recipient_scope is named_list."
            )
        return self


class LegacyMessageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=50000)
    release_trigger: ReleaseTrigger | None = None
    release_value: str | None = Field(default=None, max_length=500)
    recipient_scope: RecipientScope | None = None
    named_recipients: list[str] | None = None
    is_private: bool | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("named_recipients")
    @classmethod
    def validate_named_recipients(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return _normalize_named_recipients(values)
