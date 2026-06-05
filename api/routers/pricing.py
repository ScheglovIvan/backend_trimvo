from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.admin_config import AdminConfig

router = APIRouter(prefix="/v1/pricing", tags=["pricing"])


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
    base_5s  = _get(db, "GEMS_BASE_PER_5S", 5)
    base_10s = _get(db, "GEMS_BASE_PER_10S", 10)
    std      = _get(db, "GEMS_MULTIPLIER_STANDARD", 1)
    hd       = _get(db, "GEMS_MULTIPLIER_HD", 2)
    uhd      = _get(db, "GEMS_MULTIPLIER_ULTRA_HD", 4)
    img      = _get(db, "IMAGE_JOB_COST", 150)

    return {
        "video": {
            "5s": {
                "standard": base_5s * std,
                "hd":       base_5s * hd,
                "ultra_hd": base_5s * uhd,
            },
            "10s": {
                "standard": base_10s * std,
                "hd":       base_10s * hd,
                "ultra_hd": base_10s * uhd,
            },
        },
        "image_per_photo": img,
        "svip_discount": 0.5,
    }
