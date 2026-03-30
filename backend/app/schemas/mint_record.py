from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MintPolicyItem(BaseModel):
    package_code: str
    package_name: str
    package_lane: str
    token_type: str | None = None
    product_includes_onchain_anchor: bool
    auto_mint_enabled: bool
    opt_in_only: bool = False
    requires_customer_public_safe_approval: bool = False
    included_anchor_count: int = 0
    runtime_enabled: bool = False


class MintEligibilityResponse(BaseModel):
    project_id: str
    package_code: str
    package_lane: str
    mint_policy: MintPolicyItem
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    latest_mint_record_id: str | None = None


class PrepareMintRecordPayload(BaseModel):
    version_strategy: str = Field(default="new_version_if_needed")
    poster_style: str = Field(default="abstract_cover")
    public_title_opt_in: bool = False
    public_title: str | None = None
    public_title_kind: str = Field(default="none")


class AdminMintApprovalPayload(BaseModel):
    notes: str = ""


class CustomerMintApprovalPayload(BaseModel):
    notes: str = ""
    wallet_address: str | None = None
    approved_poster_opt_in: bool = False
    public_title_opt_in: bool = False
    public_title: str | None = None
    public_title_kind: str = Field(default="none")


class MintRecordResponse(BaseModel):
    id: str
    project_id: str
    household_id: str | None = None
    family_id: str | None = None
    user_id: str
    package_code: str
    package_lane: str
    token_type: str | None = None
    chain: str
    contract_address: str
    token_id: str | None = None
    tx_hash: str | None = None
    metadata_uri: str
    project_ref_hash: str
    household_ref_hash: str | None = None
    build_hash: str
    certificate_hash: str | None = None
    version_number: int
    poster_image_uri_public: str
    poster_style: str
    mint_status: str
    approved_at: datetime | None = None
    minted_at: datetime | None = None
    failed_at: datetime | None = None
    customer_wallet: str | None = None
    minted_by: str | None = None
    public_title_opt_in: bool = False
    public_title: str | None = None
    public_title_kind: str = "none"
    error_code: str | None = None
    error_message: str | None = None
    pending_approvals: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MintStatusResponse(BaseModel):
    project_id: str
    mint_enabled: bool
    latest: MintRecordResponse | None = None
    history: list[MintRecordResponse] = Field(default_factory=list)
