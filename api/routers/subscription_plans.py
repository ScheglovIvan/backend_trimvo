from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.subscription_plan import SubscriptionPlan
from schemas.subscription_plan import SubscriptionPlanOut, SubscriptionPlanListResponse

router = APIRouter(prefix="/v1/subscription-plans", tags=["subscription-plans"])


@router.get("", response_model=SubscriptionPlanListResponse)
def list_plans(db: Session = Depends(get_db)):
    items = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active == True)
        .order_by(SubscriptionPlan.order)
        .all()
    )
    return SubscriptionPlanListResponse(items=[SubscriptionPlanOut.model_validate(p) for p in items])
