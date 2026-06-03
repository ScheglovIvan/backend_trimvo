from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.dependencies import get_admin_user
from models.job import Job
from schemas.job import JobOut, JobListResponse

router = APIRouter(prefix="/v1/admin/jobs", tags=["admin-jobs"])


@router.get("", response_model=JobListResponse)
def list_all_jobs(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    total = query.count()
    items = query.order_by(Job.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return JobListResponse(items=[JobOut.model_validate(j) for j in items], total=total)
