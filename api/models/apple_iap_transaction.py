import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class AppleIAPTransaction(Base):
    __tablename__ = "apple_iap_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Unique per individual purchase (consumables) or per renewal (subscriptions)
    transaction_id = Column(String(255), unique=True, nullable=False)
    # Shared across all renewals of the same subscription; equals transaction_id for one-time
    original_transaction_id = Column(String(255), nullable=False, index=True)

    product_id = Column(String(255), nullable=False)
    # gem_purchase | subscription
    purchase_type = Column(String(50), nullable=False)
    quantity = Column(Integer, default=1)
    environment = Column(String(20), nullable=False)  # Sandbox | Production

    purchase_date = Column(DateTime(timezone=True), nullable=True)
    expires_date = Column(DateTime(timezone=True), nullable=True)

    # processed | refunded | revoked | expired
    status = Column(String(50), default="processed", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
