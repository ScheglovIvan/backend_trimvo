from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ConfigOut(BaseModel):
    key: str
    value: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StubConfigUpdate(BaseModel):
    stub_latency_ms: Optional[int] = None
    stub_success_rate: Optional[float] = None
    stub_mode: Optional[bool] = None


class ModelConfigUpdate(BaseModel):
    ai_endpoint: Optional[str] = None
    ai_token: Optional[str] = None


class AuditLogOut(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    entity: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}
