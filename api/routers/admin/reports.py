from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from core.database import get_db
from core.dependencies import get_admin_user
from models.report import Report
from models.template import Template
from models.user import User
from schemas.report import ReportUpdate, ReportListResponse, ReportOut
from services import storage

router = APIRouter(prefix="/v1/admin/reports", tags=["admin-reports"])


def _signed(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        return storage.get_signed_url(storage.settings.r2_bucket_templates, path)
    except Exception:
        return None


def _to_out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id,
        template_id=r.template_id,
        template_title=r.template.title if r.template else None,
        template_thumb_url=_signed(r.template.thumb_path) if r.template else None,
        user_id=r.user_id,
        user_email=r.user.email if r.user else None,
        reason=r.reason,
        description=r.description,
        status=r.status,
        created_at=r.created_at,
    )


@router.get("", response_model=ReportListResponse)
def list_reports(
    status: Optional[str] = None,
    template_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    query = db.query(Report)
    if status:
        query = query.filter(Report.status == status)
    if template_id:
        query = query.filter(Report.template_id == template_id)
    query = query.order_by(Report.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return ReportListResponse(items=[_to_out(r) for r in items], total=total)


@router.put("/{report_id}")
def update_report(
    report_id: UUID,
    body: ReportUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    if body.status not in ("pending", "reviewed", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status")
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    r.status = body.status
    db.commit()
    db.refresh(r)
    return _to_out(r)
