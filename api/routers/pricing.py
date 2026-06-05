from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.admin_config import AdminConfig

router = APIRouter(prefix="/v1/pricing", tags=["pricing"])

IMAGE_JOB_DEFAULT_COST = 150


def _get(db: Session, key: str, default: int) -> int:
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    if row:
        try:
            return int(row.value)
        except (ValueError, TypeError):
            pass
    return default


@router.get("")
def get_pricing(db: Session = Depends(get_db)):
    image_cost = _get(db, "IMAGE_JOB_COST", IMAGE_JOB_DEFAULT_COST)
    return {
        "image_job_cost_per_image": image_cost,
    }
