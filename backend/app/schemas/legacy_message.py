from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

MessageType = Literal["letter", "time_capsule", "open_when", "family_principle", "voice_note", "memory_prompt", "lineage_milestone", "heirloom_assignment", "legacy_handoff", "descendant_story_branch"]

class LegacyMessageCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=50000)
    message_type: MessageType = Field(default="letter")
    release_trigger: Literal["on_death", "on_date", "on_age_milestone", "open_when", "immediate", "manual"] = Field(default="manual")
    release_value: Optional[str] = Field(default=None, max_length=500)
    recipient_scope: Literal["descendants", "spouse", "named_list", "household", "all_linked", "public"] = Field(default="descendants")
    named_recipients: list[str] = Field(default_factory=list)
    branch_tag: Optional[str] = Field(default=None, max_length=100)
    is_private: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)

class LegacyMessageUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    content: Optional[str] = Field(default=None, min_length=1, max_length=50000)
    release_trigger: Optional[str] = None
    release_value: Optional[str] = Field(default=None, max_length=500)
    recipient_scope: Optional[str] = None
    named_recipients: Optional[list[str]] = None
    is_private: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None
