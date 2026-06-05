from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from core.database import get_db
from core.dependencies import get_admin_user
from models.admin_config import AdminConfig

router = APIRouter(prefix="/v1/admin/pricing", tags=["admin-pricing"])


class PricingConfig(BaseModel):
    gems_base_per_10s: Optional[int] = None
    gems_base_per_5s: Optional[int] = None
    gems_extra_standard: Optional[int] = None
    gems_extra_hd: Optional[int] = None
    gems_extra_ultra_hd: Optional[int] = None
    image_job_cost: Optional[int] = None


def _get(db, key, default):
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    return int(row.value) if row else default


def _set(db, key, value, admin_id):
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    if row:
        row.value = str(value)
        row.updated_by = admin_id
    else:
        db.add(AdminConfig(key=key, value=str(value), updated_by=admin_id))
    db.commit()


@router.get("")
def get_pricing(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    base_5s    = _get(db, "GEMS_BASE_PER_5S", 5)
    base_10s   = _get(db, "GEMS_BASE_PER_10S", 10)
    std        = _get(db, "GEMS_EXTRA_STANDARD", 0)
    hd         = _get(db, "GEMS_EXTRA_HD", 10)
    uhd        = _get(db, "GEMS_EXTRA_ULTRA_HD", 25)
    image_cost = _get(db, "IMAGE_JOB_COST", 150)
    return {
        "gems_base_per_5s": base_5s,
        "gems_base_per_10s": base_10s,
        "gems_extra_standard": std,
        "gems_extra_hd": hd,
        "gems_extra_ultra_hd": uhd,
        "image_job_cost": image_cost,
        "examples": {
            "5s_standard":  base_5s  + std,
            "5s_hd":        base_5s  + hd,
            "5s_ultra_hd":  base_5s  + uhd,
            "10s_standard": base_10s + std,
            "10s_hd":       base_10s + hd,
            "10s_ultra_hd": base_10s + uhd,
            "image_1x":     image_cost,
            "image_4x":     image_cost * 4,
            "svip_discount": "50%",
        }
    }


@router.put("")
def update_pricing(
    body: PricingConfig,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    if body.gems_base_per_5s is not None:
        _set(db, "GEMS_BASE_PER_5S", body.gems_base_per_5s, admin.id)
    if body.gems_base_per_10s is not None:
        _set(db, "GEMS_BASE_PER_10S", body.gems_base_per_10s, admin.id)
    if body.gems_extra_standard is not None:
        _set(db, "GEMS_EXTRA_STANDARD", body.gems_extra_standard, admin.id)
    if body.gems_extra_hd is not None:
        _set(db, "GEMS_EXTRA_HD", body.gems_extra_hd, admin.id)
    if body.gems_extra_ultra_hd is not None:
        _set(db, "GEMS_EXTRA_ULTRA_HD", body.gems_extra_ultra_hd, admin.id)
    if body.image_job_cost is not None:
        _set(db, "IMAGE_JOB_COST", body.image_job_cost, admin.id)
    return {"success": True}
