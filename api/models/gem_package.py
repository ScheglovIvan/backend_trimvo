import uuid
from sqlalchemy import Column, String, Integer, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base


class GemPackage(Base):
    __tablename__ = "gem_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gems_amount = Column(Integer, nullable=False)
    bonus_gems = Column(Integer, default=0)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default="UAH")
    label = Column(String(100))
    is_popular = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    apple_product_id = Column(String(200))
    google_product_id = Column(String(200))
    order = Column(Integer, default=0)
