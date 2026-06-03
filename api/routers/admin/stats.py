from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from core.database import get_db
from core.dependencies import get_admin_user
from models.user import User
from models.gem_transaction import GemTransaction

router = APIRouter(prefix="/v1/admin/stats", tags=["admin-stats"])


@router.get("/gems")
def gem_stats(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_in_circulation = db.query(func.sum(User.gems)).scalar() or 0

    purchased_today = db.query(func.sum(GemTransaction.amount))\
        .filter(
            GemTransaction.type == "purchase",
            GemTransaction.created_at >= today_start,
        ).scalar() or 0

    spent_today = db.query(func.sum(GemTransaction.amount))\
        .filter(
            GemTransaction.type == "generation",
            GemTransaction.created_at >= today_start,
        ).scalar() or 0

    refunds_today = db.query(func.sum(GemTransaction.amount))\
        .filter(
            GemTransaction.type == "refund",
            GemTransaction.created_at >= today_start,
        ).scalar() or 0

    users_with_zero = db.query(func.count(User.id)).filter(User.gems == 0).scalar() or 0

    return {
        "total_gems_in_circulation": total_in_circulation,
        "total_gems_purchased_today": purchased_today,
        "total_gems_spent_today": abs(spent_today),
        "total_refunds_today": refunds_today,
        "users_with_zero_gems": users_with_zero,
    }
