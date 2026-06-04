from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from core.database import get_db
from core.dependencies import get_admin_user
from models.trend import Trend
from schemas.template import TrendOut, TrendCreate

router = APIRouter(prefix="/v1/admin/trends", tags=["admin-trends"])


@router.get("", response_model=List[TrendOut])
def list_trends(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    return [TrendOut.model_validate(t) for t in db.query(Trend).filter(Trend.template_id.isnot(None)).order_by(Trend.order).all()]


@router.post("", response_model=TrendOut)
def create_trend(body: TrendCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    t = Trend(template_id=body.template_id, order=body.order)
    db.add(t)
    db.commit()
    db.refresh(t)
    return TrendOut.model_validate(t)


@router.put("/{trend_id}", response_model=TrendOut)
def update_trend(trend_id: UUID, body: TrendCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    t = db.query(Trend).filter(Trend.id == trend_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    t.order = body.order
    db.commit()
    db.refresh(t)
    return TrendOut.model_validate(t)


@router.delete("/{trend_id}")
def delete_trend(trend_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    t = db.query(Trend).filter(Trend.id == trend_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(t)
    db.commit()
    return {"success": True}
