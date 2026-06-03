from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID
from datetime import datetime

ALLOWED_RESOLUTIONS = {"720x1280", "1080x1920", "1920x1080", "2160x3840"}
ALLOWED_QUALITIES = {"standard", "high", "premium"}
ALLOWED_FORMATS = {"mp4", "mov"}

CUSTOM_JOB_COST: Dict[str, int] = {
    "standard": 300,
    "high": 600,
    "premium": 1200,
}


class JobOptions(BaseModel):
    quality: Optional[str] = None
    orientation: Optional[str] = None
    prompt: Optional[str] = None
    photo_url: Optional[str] = None
    photo_url_male: Optional[str] = None
    photo_url_female: Optional[str] = None
    template_image_url: Optional[str] = None


class JobCreate(BaseModel):
    template_id: UUID
    options: Optional[JobOptions] = None
    quality: Optional[str] = "standard"
    duration_seconds: Optional[int] = 10


class CustomJobParams(BaseModel):
    prompt: str
    resolution: str = "1080x1920"
    quality: str = "standard"
    format: str = "mp4"

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        if v not in ALLOWED_RESOLUTIONS:
            raise ValueError(f"resolution must be one of {sorted(ALLOWED_RESOLUTIONS)}")
        return v

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        if v not in ALLOWED_QUALITIES:
            raise ValueError(f"quality must be one of {sorted(ALLOWED_QUALITIES)}")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in ALLOWED_FORMATS:
            raise ValueError(f"format must be one of {sorted(ALLOWED_FORMATS)}")
        return v


class JobOut(BaseModel):
    id: UUID
    user_id: UUID
    template_id: Optional[UUID] = None
    status: str
    progress: int
    result_path: Optional[str] = None
    preview_url: Optional[str] = None
    thumb_url: Optional[str] = None
    original_url: Optional[str] = None
    error: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    job_type: str = "template"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: str
    gems_cost: int = 0


class JobStatusResponse(BaseModel):
    status: str
    progress: int
    result_url: Optional[str] = None
    preview_url: Optional[str] = None
    thumb_url: Optional[str] = None
    original_url: Optional[str] = None
    result_urls: Optional[List[str]] = None
    error: Optional[str] = None


class JobListResponse(BaseModel):
    items: List[JobOut]
    total: int
