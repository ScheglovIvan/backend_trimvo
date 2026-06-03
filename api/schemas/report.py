from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

VALID_REASONS = {
    "involves_minor", "sexual_content", "harassment",
    "hate_discrimination", "violence", "self_harm",
    "real_person", "illegal_activity", "copyright", "spam", "other",
}


class ReportCreate(BaseModel):
    template_id: UUID
    reason: str
    description: Optional[str] = None


class ReportUpdate(BaseModel):
    status: str


class ReportOut(BaseModel):
    id: UUID
    template_id: UUID
    template_title: Optional[str] = None
    template_thumb_url: Optional[str] = None
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    reason: str
    description: Optional[str] = None
    status: str
    created_at: datetime


class ReportListResponse(BaseModel):
    items: List[ReportOut]
    total: int
