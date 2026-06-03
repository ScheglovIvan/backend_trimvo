import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL"))
    status = Column(String(20), default="queued")
    progress = Column(Integer, default=0)
    result_path = Column(String(500))
    preview_url = Column(String(500))
    thumb_url = Column(String(500))
    original_url = Column(String(500))
    error = Column(Text)
    options = Column(JSONB)
    gems_cost = Column(Integer, default=0)
    quality = Column(String(20), default="standard")
    duration_seconds = Column(Integer, default=10)
    job_type = Column(String(20), nullable=False, default="template")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="jobs")
    template = relationship("Template", back_populates="jobs")
