from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from core.config import get_settings
from models.admin_config import AdminConfig

router = APIRouter(prefix="/v1/config", tags=["config"])
settings = get_settings()


def _pub(path: str) -> str:
    return f"{settings.r2_public_url_templates}/{path.lstrip('/')}"


@router.get("/onboarding-video")
def get_onboarding_video_public(db: Session = Depends(get_db)):
    row = db.query(AdminConfig).filter(
        AdminConfig.key == "ONBOARDING_VIDEO"
    ).first()
    url = _pub(row.value) if row and row.value else None
    return {"url": url}
