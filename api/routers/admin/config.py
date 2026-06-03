from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from core.database import get_db
from core.config import get_settings
from core.dependencies import get_admin_user
from models.admin_config import AdminConfig
from models.user import User
from schemas.admin_config import StubConfigUpdate, ModelConfigUpdate
from services import storage as stor

settings = get_settings()


def _pub(path: str) -> str:
    return f"{settings.r2_public_url_templates}/{path.lstrip('/')}"

router = APIRouter(prefix="/v1/admin/config", tags=["admin-config"])


def _get_config(db: Session, key: str, default: str = "") -> str:
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    return row.value if row else default


def _set_config(db: Session, key: str, value: str, user_id=None):
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    if row:
        row.value = value
        row.updated_by = user_id
    else:
        db.add(AdminConfig(key=key, value=value, updated_by=user_id))
    db.commit()


@router.get("/stub")
def get_stub_config(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    return {
        "stub_mode": _get_config(db, "STUB_MODE", "true"),
        "stub_latency_ms": _get_config(db, "STUB_LATENCY_MS", "10000"),
        "stub_success_rate": _get_config(db, "STUB_SUCCESS_RATE", "0.8"),
    }


@router.put("/stub")
def update_stub_config(
    body: StubConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if body.stub_mode is not None:
        _set_config(db, "STUB_MODE", str(body.stub_mode).lower(), admin.id)
    if body.stub_latency_ms is not None:
        _set_config(db, "STUB_LATENCY_MS", str(body.stub_latency_ms), admin.id)
    if body.stub_success_rate is not None:
        _set_config(db, "STUB_SUCCESS_RATE", str(body.stub_success_rate), admin.id)
    return {"success": True}


@router.get("/models")
def get_model_config(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    return {
        "ai_endpoint": _get_config(db, "AI_ENDPOINT", ""),
        "ai_token": _get_config(db, "AI_TOKEN", ""),
    }


@router.put("/models")
def update_model_config(
    body: ModelConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if body.ai_endpoint is not None:
        _set_config(db, "AI_ENDPOINT", body.ai_endpoint, admin.id)
    if body.ai_token is not None:
        _set_config(db, "AI_TOKEN", body.ai_token, admin.id)
    return {"success": True}


ONBOARDING_KEY = "ONBOARDING_VIDEO"


@router.get("/onboarding-video")
def get_onboarding_video(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    path = _get_config(db, ONBOARDING_KEY, "")
    return {
        "url": _pub(path) if path else None,
        "has_video": bool(path),
    }


@router.post("/onboarding-video")
async def upload_onboarding_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    data = await video.read()
    bucket = settings.r2_bucket_templates

    ext = "mp4"
    if video.content_type and "gif" in video.content_type:
        ext = "gif"

    path = f"onboarding/background.{ext}"
    stor.upload_file(bucket, path, data, video.content_type or "video/mp4")
    _set_config(db, ONBOARDING_KEY, path, admin.id)

    return {"url": _pub(path), "has_video": True}


@router.delete("/onboarding-video")
def delete_onboarding_video(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    row = db.query(AdminConfig).filter(
        AdminConfig.key == ONBOARDING_KEY
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return {"success": True}
