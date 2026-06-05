from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models.user import User
from models.gem_transaction import GemTransaction
from models.admin_config import AdminConfig
from fastapi import HTTPException


def get_config_int(db: Session, key: str, default: int) -> int:
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    try:
        return int(row.value) if row else default
    except (ValueError, TypeError):
        return default


def apply_svip_discount(cost: int, user: User) -> int:
    if user.subscription_status == "svip":
        if user.subscription_expires_at is None or \
           user.subscription_expires_at > datetime.now(timezone.utc):
            return max(1, cost // 2)
    return cost


def deduct_gems(
    db: Session,
    user: User,
    amount: int,
    description: str,
    reference_id: str = None,
) -> GemTransaction:
    if user.gems < amount:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient gems. Required: {amount}, available: {user.gems}"
        )
    user.gems -= amount
    tx = GemTransaction(
        user_id=user.id,
        amount=-amount,
        balance_after=user.gems,
        type="generation",
        description=description,
        reference_id=reference_id,
    )
    db.add(tx)
    db.commit()
    return tx


def add_gems(
    db: Session,
    user: User,
    amount: int,
    tx_type: str,
    description: str,
    reference_id: str = None,
) -> GemTransaction:
    user.gems += amount
    tx = GemTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.gems,
        type=tx_type,
        description=description,
        reference_id=reference_id,
    )
    db.add(tx)
    db.commit()
    return tx


def refund_gems(db: Session, user: User, amount: int, reference_id: str):
    return add_gems(
        db, user, amount,
        tx_type="refund",
        description="Refund for failed job",
        reference_id=reference_id,
    )
