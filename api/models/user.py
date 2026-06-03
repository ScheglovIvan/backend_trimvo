import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    gems = Column(Integer, default=0)
    subscription_status = Column(String(20), default="free")
    subscription_expires_at = Column(DateTime, nullable=True)
    is_banned = Column(Boolean, default=False, nullable=False, server_default="false")
    google_id = Column(String(255), unique=True, nullable=True)
    apple_id = Column(String(255), unique=True, nullable=True)
    name = Column(String(255), nullable=True)
    last_daily_bonus_at = Column(DateTime, nullable=True)
    referral_code = Column(String(20), unique=True, nullable=True)
    referred_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    jobs = relationship("Job", back_populates="user")
    gem_transactions = relationship("GemTransaction", back_populates="user")
