from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicCheckoutOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_code: str | None = Field(default=None)
    package_slug: str | None = Field(default=None)
    stripe_session_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_package_identity(self):
        if not (self.package_code or self.package_slug or self.stripe_session_id):
            raise ValueError("package_code or package_slug is required.")
        return self


class AdminManualOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str = Field(..., min_length=3)
    package_code: str | None = Field(default=None)
    package_slug: str | None = Field(default=None)
    project_id: Optional[str] = None
    reason: str = Field(..., min_length=3)
    authorization_source: str = Field(..., min_length=3)
    idempotency_key: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def validate_package_identity(self):
        if not (self.package_code or self.package_slug):
            raise ValueError("package_code or package_slug is required.")
        return self


class OrderResponse(BaseModel):
    id: str
    user_id: str
    email: str
    package_code: str
    package_slug: str
    package_name: str
    price_label: str
    item_type: str
    billing_plan: str
    source: str
    status: str
    project_id: Optional[str] = None
    stripe_session_id: Optional[str] = None
    stripe_payment_link_id: Optional[str] = None
    fulfillment_status: Optional[str] = None
    created_at: datetime


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
