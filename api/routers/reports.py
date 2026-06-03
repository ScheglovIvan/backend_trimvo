from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.security import decode_token
from models.report import Report
from models.user import User
from models.template import Template
from schemas.report import ReportCreate

router = APIRouter(prefix="/v1/reports", tags=["reports"])

_bearer = HTTPBearer(auto_error=False)


@router.post("")
def create_report(
    body: ReportCreate,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    template = db.query(Template).filter(Template.id == body.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    user_id = None
    if credentials:
        uid = decode_token(credentials.credentials)
        if uid:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                user_id = user.id

    report = Report(
        template_id=body.template_id,
        user_id=user_id,
        reason=body.reason,
        description=body.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": str(report.id), "status": "received"}
