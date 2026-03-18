from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    package_slug: str = Field(..., min_length=1)
    package_name: str = Field(..., min_length=1)
    price_label: str = Field(..., min_length=1)
    source: str = Field(default="stripe_payment_link")
    order_status: str = Field(default="paid")
    stripe_session_id: Optional[str] = None
    stripe_payment_link_id: Optional[str] = None


class OrderResponse(BaseModel):
    id: str
    user_id: str
    email: str
    package_slug: str
    package_name: str
    price_label: str
    source: str
    status: str
    stripe_session_id: Optional[str] = None
    stripe_payment_link_id: Optional[str] = None
    created_at: datetime


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]