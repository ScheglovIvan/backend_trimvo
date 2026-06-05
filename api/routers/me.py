from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from core.database import get_db
from core.dependencies import get_current_user
from models.user import User
from models.gem_transaction import GemTransaction
from models.job import Job
from models.admin_config import AdminConfig, AuditLog
from models.report import Report
from models.template import Template
from services.gems import add_gems, get_config_int

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("/gems")
def get_gems_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription_active = (
        current_user.subscription_status in ("svip", "vip") and
        (current_user.subscription_expires_at is None or
         current_user.subscription_expires_at > datetime.now(timezone.utc))
    )
    return {
        "gems": current_user.gems,
        "subscription_status": current_user.subscription_status,
        "subscription_expires_at": current_user.subscription_expires_at,
        "subscription_active": subscription_active,
    }


@router.post("/daily-bonus")
def claim_daily_bonus(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    if current_user.last_daily_bonus_at:
        last = current_user.last_daily_bonus_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < timedelta(hours=24):
            next_bonus = last + timedelta(hours=24)
            raise HTTPException(
                status_code=400,
                detail=f"Daily bonus already claimed. Next available at {next_bonus.isoformat()}"
            )

    base_bonus = get_config_int(db, "GEMS_DAILY_BONUS", 5)
    amount = base_bonus * 2 if current_user.subscription_status == "svip" else base_bonus

    current_user.last_daily_bonus_at = now
    add_gems(db, current_user, amount, tx_type="bonus", description="Daily bonus")

    return {"gems_awarded": amount, "new_balance": current_user.gems}


@router.delete("/account", status_code=204)
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id

    # Обнуляем nullable FK-ссылки на пользователя
    db.query(AdminConfig).filter(AdminConfig.updated_by == uid).update({"updated_by": None})
    db.query(AuditLog).filter(AuditLog.user_id == uid).update({"user_id": None})
    db.query(Report).filter(Report.user_id == uid).update({"user_id": None})
    db.query(Template).filter(Template.created_by == uid).update({"created_by": None})

    # Удаляем записи пользователя
    db.query(GemTransaction).filter(GemTransaction.user_id == uid).delete()
    db.query(Job).filter(Job.user_id == uid).delete()

    db.delete(current_user)
    db.commit()


@router.get("/transactions")
def get_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(GemTransaction)\
          .filter(GemTransaction.user_id == current_user.id)\
          .order_by(GemTransaction.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "balance_after": t.balance_after,
                "type": t.type,
                "description": t.description,
                "reference_id": t.reference_id,
                "created_at": t.created_at,
            }
            for t in items
        ],
        "total": total,
    }
