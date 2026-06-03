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
    gems_multiplier_standard: Optional[int] = None
    gems_multiplier_hd: Optional[int] = None
    gems_multiplier_ultra_hd: Optional[int] = None


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
    base_10s = _get(db, "GEMS_BASE_PER_10S", 10)
    base_5s  = _get(db, "GEMS_BASE_PER_5S", 5)
    std      = _get(db, "GEMS_MULTIPLIER_STANDARD", 1)
    hd       = _get(db, "GEMS_MULTIPLIER_HD", 2)
    uhd      = _get(db, "GEMS_MULTIPLIER_ULTRA_HD", 4)
    return {
        "gems_base_per_10s": base_10s,
        "gems_base_per_5s": base_5s,
        "gems_multiplier_standard": std,
        "gems_multiplier_hd": hd,
        "gems_multiplier_ultra_hd": uhd,
        "examples": {
            "5s_standard":   base_5s  * std,
            "5s_hd":         base_5s  * hd,
            "5s_ultra_hd":   base_5s  * uhd,
            "10s_standard":  base_10s * std,
            "10s_hd":        base_10s * hd,
            "10s_ultra_hd":  base_10s * uhd,
            "svip_discount": "50%",
        }
    }


@router.put("")
def update_pricing(
    body: PricingConfig,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    if body.gems_base_per_10s is not None:
        _set(db, "GEMS_BASE_PER_10S", body.gems_base_per_10s, admin.id)
    if body.gems_base_per_5s is not None:
        _set(db, "GEMS_BASE_PER_5S", body.gems_base_per_5s, admin.id)
    if body.gems_multiplier_standard is not None:
        _set(db, "GEMS_MULTIPLIER_STANDARD", body.gems_multiplier_standard, admin.id)
    if body.gems_multiplier_hd is not None:
        _set(db, "GEMS_MULTIPLIER_HD", body.gems_multiplier_hd, admin.id)
    if body.gems_multiplier_ultra_hd is not None:
        _set(db, "GEMS_MULTIPLIER_ULTRA_HD", body.gems_multiplier_ultra_hd, admin.id)
    return {"success": True}
