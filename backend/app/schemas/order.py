from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class OrderCreate(BaseModel):
    package_code: str | None = Field(default=None)
    package_slug: str | None = Field(default=None)
    package_name: str = Field(..., min_length=1)
    price_label: str = Field(..., min_length=1)
    item_type: str = Field(default="package")
    billing_plan: str = Field(default="one_time")
    source: str = Field(default="stripe_payment_link")
    order_status: str = Field(default="paid")
    stripe_session_id: Optional[str] = None
    stripe_payment_link_id: Optional[str] = None

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
    created_at: datetime


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]