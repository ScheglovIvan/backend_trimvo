import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from uuid import UUID
from pydantic import BaseModel
from core.database import get_db
from models.user import User
from models.gem_transaction import GemTransaction
from services.gems import add_gems

router = APIRouter(prefix="/v1/payments", tags=["payments"])


class WebhookPayload(BaseModel):
    user_id: UUID
    gems_amount: int
    product_id: str
    payment_id: str


@router.post("/webhook")
def payment_webhook(
    body: WebhookPayload,
    db: Session = Depends(get_db),
    x_signature: str = Header(None),
):
    existing = db.query(GemTransaction).filter(
        GemTransaction.reference_id == body.payment_id,
        GemTransaction.type == "purchase",
    ).first()
    if existing:
        return {"success": True, "duplicate": True}

    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    add_gems(
        db, user, body.gems_amount,
        tx_type="purchase",
        description=f"Purchase: {body.product_id}",
        reference_id=body.payment_id,
    )
    return {"success": True}
