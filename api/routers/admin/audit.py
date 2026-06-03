from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from core.dependencies import get_admin_user
from models.admin_config import AuditLog
from schemas.admin_config import AuditLogOut

router = APIRouter(prefix="/v1/admin", tags=["admin-audit"])


@router.get("/audit-log", response_model=List[AuditLogOut])
def get_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    items = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return [AuditLogOut.model_validate(i) for i in items]
