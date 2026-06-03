from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from core.database import get_db
from core.dependencies import get_admin_user
from models.subscription_plan import SubscriptionPlan
from schemas.subscription_plan import (
    SubscriptionPlanCreate, SubscriptionPlanUpdate,
    SubscriptionPlanOut, SubscriptionPlanListResponse,
)

router = APIRouter(prefix="/v1/admin/subscription-plans", tags=["admin-subscription-plans"])


@router.get("", response_model=SubscriptionPlanListResponse)
def list_plans(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    items = db.query(SubscriptionPlan).order_by(SubscriptionPlan.order).all()
    return SubscriptionPlanListResponse(items=[SubscriptionPlanOut.model_validate(p) for p in items])


@router.post("", response_model=SubscriptionPlanOut)
def create_plan(body: SubscriptionPlanCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    plan = SubscriptionPlan(**body.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return SubscriptionPlanOut.model_validate(plan)


@router.put("/{plan_id}", response_model=SubscriptionPlanOut)
def update_plan(plan_id: UUID, body: SubscriptionPlanUpdate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(plan, field, val)
    db.commit()
    db.refresh(plan)
    return SubscriptionPlanOut.model_validate(plan)


@router.delete("/{plan_id}")
def delete_plan(plan_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(plan)
    db.commit()
    return {"success": True}
