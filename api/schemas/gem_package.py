from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


class GemPackageCreate(BaseModel):
    gems_amount: int
    bonus_gems: int = 0
    price: float
    currency: str = "UAH"
    label: Optional[str] = None
    is_popular: bool = False
    is_active: bool = True
    apple_product_id: Optional[str] = None
    google_product_id: Optional[str] = None
    order: int = 0


class GemPackageUpdate(BaseModel):
    gems_amount: Optional[int] = None
    bonus_gems: Optional[int] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    label: Optional[str] = None
    is_popular: Optional[bool] = None
    is_active: Optional[bool] = None
    apple_product_id: Optional[str] = None
    google_product_id: Optional[str] = None
    order: Optional[int] = None


class GemPackageOut(BaseModel):
    id: UUID
    gems_amount: int
    bonus_gems: int
    price: float
    currency: str
    label: Optional[str] = None
    is_popular: bool
    is_active: bool
    apple_product_id: Optional[str] = None
    google_product_id: Optional[str] = None
    order: int

    model_config = {"from_attributes": True}


class GemPackageListResponse(BaseModel):
    items: List[GemPackageOut]
