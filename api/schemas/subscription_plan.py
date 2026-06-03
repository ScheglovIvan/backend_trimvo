from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


class SubscriptionPlanCreate(BaseModel):
    name: str
    tier: str
    period: str
    price: float
    currency: str = "UAH"
    bonus_gems: int = 0
    discount_percent: int = 0
    apple_product_id: Optional[str] = None
    google_product_id: Optional[str] = None
    is_active: bool = True
    order: int = 0


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    tier: Optional[str] = None
    period: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    bonus_gems: Optional[int] = None
    discount_percent: Optional[int] = None
    apple_product_id: Optional[str] = None
    google_product_id: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None


class SubscriptionPlanOut(BaseModel):
    id: UUID
    name: str
    tier: str
    period: str
    price: float
    currency: str
    bonus_gems: int
    discount_percent: int
    apple_product_id: Optional[str] = None
    google_product_id: Optional[str] = None
    is_active: bool
    order: int

    model_config = {"from_attributes": True}


class SubscriptionPlanListResponse(BaseModel):
    items: List[SubscriptionPlanOut]
