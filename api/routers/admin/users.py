from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from core.database import get_db
from core.dependencies import get_admin_user
from models.user import User
from models.gem_transaction import GemTransaction
from services.gems import add_gems

router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])


class UserOut(BaseModel):
    id: UUID
    email: str
    name: Optional[str] = None
    gems: int
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None
    is_banned: bool = False
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: List[UserOut]
    total: int


class AdjustGemsBody(BaseModel):
    amount: int
    description: str


class UpdateSubscriptionBody(BaseModel):
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    subscription: Optional[str] = None,
    is_banned: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    q = db.query(User)
    if search:
        q = q.filter(User.email.ilike(f"%{search}%"))
    if subscription:
        q = q.filter(User.subscription_status == subscription)
    if is_banned is not None:
        q = q.filter(User.is_banned == is_banned)
    total = q.count()
    items = q.order_by(User.created_at.desc())\
             .offset((page - 1) * per_page).limit(per_page).all()
    return UserListResponse(
        items=[UserOut.model_validate(u) for u in items],
        total=total,
    )


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Not found")
    return UserOut.model_validate(u)


@router.post("/{user_id}/gems")
def adjust_gems(
    user_id: UUID,
    body: AdjustGemsBody,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Not found")

    if body.amount < 0 and u.gems < abs(body.amount):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot remove {abs(body.amount)} gems, user only has {u.gems}"
        )

    add_gems(
        db, u, body.amount,
        tx_type="admin_adjustment",
        description=f"Admin adjustment: {body.description}",
        reference_id=str(admin.id),
    )
    return {"success": True, "new_balance": u.gems}


@router.put("/{user_id}/subscription")
def update_subscription(
    user_id: UUID,
    body: UpdateSubscriptionBody,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Not found")
    u.subscription_status = body.subscription_status
    u.subscription_expires_at = body.subscription_expires_at
    db.commit()
    return {"success": True}


@router.post("/{user_id}/ban")
def ban_user(user_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Not found")
    if u.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot ban admin")
    u.is_banned = True
    db.commit()
    return {"success": True}


@router.post("/{user_id}/unban")
def unban_user(user_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Not found")
    u.is_banned = False
    db.commit()
    return {"success": True}


@router.get("/{user_id}/transactions")
def get_user_transactions(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    q = db.query(GemTransaction)\
          .filter(GemTransaction.user_id == user_id)\
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
