from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AppleVerifyPurchaseRequest(BaseModel):
    signed_transaction: str


class AppleVerifySubscriptionRequest(BaseModel):
    signed_transaction: str


class AppleRestoreRequest(BaseModel):
    signed_transactions: List[str]


class AppleVerifyPurchaseResponse(BaseModel):
    success: bool
    transaction_id: str
    product_id: str
    gems_added: int
    new_balance: int


class AppleVerifySubscriptionResponse(BaseModel):
    success: bool
    transaction_id: str
    product_id: str
    subscription_status: str
    expires_at: Optional[datetime]
    bonus_gems_added: int


class AppleRestoreItem(BaseModel):
    transaction_id: str
    product_id: str
    purchase_type: str  # gem_purchase | subscription
    already_processed: bool


class AppleRestoreResponse(BaseModel):
    restored: List[AppleRestoreItem]


class AppleNotificationRequest(BaseModel):
    signedPayload: str
