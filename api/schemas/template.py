from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class TemplateBase(BaseModel):
    title: str
    description: Optional[str] = None


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    likes: Optional[int] = None
    plays: Optional[int] = None


class TemplateOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    thumb_url: Optional[str] = None
    preview_url: Optional[str] = None
    preview_compressed_url: Optional[str] = None
    gif_url: Optional[str] = None
    likes: int
    plays: int
    is_active: bool
    created_at: datetime
    gems_cost: int = 200
    photo_slots: int = 1
    has_male_slot: bool = False
    has_female_slot: bool = False

    model_config = {"from_attributes": True}


class TemplateDetail(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    thumb_url: Optional[str] = None
    preview_url: Optional[str] = None
    preview_compressed_url: Optional[str] = None
    gif_url: Optional[str] = None
    video_url: Optional[str] = None
    likes: int
    plays: int
    is_active: bool
    created_at: datetime
    created_by: Optional[UUID] = None
    gems_cost: int = 200
    photo_slots: int = 1
    has_male_slot: bool = False
    has_female_slot: bool = False

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: List[TemplateOut]
    total: int


class CategoryBase(BaseModel):
    name: str
    order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None


class CategoryOut(BaseModel):
    id: UUID
    name: str
    order: int

    model_config = {"from_attributes": True}


class TrendOut(BaseModel):
    id: UUID
    template_id: UUID
    order: int

    model_config = {"from_attributes": True}


class TrendCreate(BaseModel):
    template_id: UUID
    order: int = 0
