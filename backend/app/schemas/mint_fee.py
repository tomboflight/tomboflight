from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MintFeeQuotePayload(BaseModel):
    minting_service_fee_usd: float = Field(default=0, ge=0)
    blockchain_network_fee_usd: float = Field(default=0, ge=0)
    network_fee_quote_usd: float = Field(default=0, ge=0)
    quote_ttl_minutes: int = Field(default=60, ge=5, le=10080)
    mint_fee_notes: str = Field(default="")


class MintFeeMarkPaidPayload(BaseModel):
    mint_fee_notes: str = Field(default="")


class MintFeeWaivePayload(BaseModel):
    mint_fee_notes: str = Field(default="")


class MintFeeRefreshNetworkQuotePayload(BaseModel):
    network_fee_quote_usd: float = Field(default=0, ge=0)
    quote_ttl_minutes: int = Field(default=60, ge=5, le=10080)
    mint_fee_notes: str = Field(default="")


class MintFeeSummaryResponse(BaseModel):
    project_id: str
    mint_fee_model: str
    minting_included: bool
    included_anchor_count: int
    mints_used_count: int
    minting_service_fee_usd: float
    blockchain_network_fee_usd: float
    additional_mint_service_fee_usd: float
    remint_service_fee_usd: float
    network_fee_quote_usd: float
    network_fee_quote_expires_at: datetime | None = None
    mint_fee_status: str
    mint_fee_paid_at: datetime | None = None
    network_fee_locked_at: datetime | None = None
    mint_fee_notes: str
