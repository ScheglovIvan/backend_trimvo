import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    video_path = Column(String(500))
    thumb_path = Column(String(500))
    gif_path = Column(String(500))
    preview_path = Column(String(500))
    preview_compressed_path = Column(String(500), nullable=True)
    status = Column(String(20), default="ready")
    likes = Column(Integer, default=0)
    plays = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    gems_cost = Column(Integer, default=200)
    photo_slots = Column(Integer, default=1)
    has_male_slot = Column(Boolean, default=False)
    has_female_slot = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    jobs = relationship("Job", back_populates="template", cascade="all, delete-orphan", passive_deletes=True)
    categories = relationship(
        "CategoryTemplate",
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    trends = relationship("Trend", back_populates="template")
    reports = relationship("Report", back_populates="template", cascade="all, delete-orphan", passive_deletes=True)
