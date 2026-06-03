import uuid
from sqlalchemy import Column, String, Integer, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100))
    tier = Column(String(20))
    period = Column(String(20))
    price = Column(Numeric(10, 2))
    currency = Column(String(10), default="UAH")
    bonus_gems = Column(Integer, default=0)
    discount_percent = Column(Integer, default=0)
    apple_product_id = Column(String(200))
    google_product_id = Column(String(200))
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
