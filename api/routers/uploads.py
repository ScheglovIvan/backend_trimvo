import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from core.dependencies import get_current_user
from models.user import User
from services.storage import upload_file, get_signed_url, settings as storage_settings

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])

_ALLOWED = {"image/jpeg", "image/png", "image/webp"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/photo")
async def upload_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in _ALLOWED:
        raise HTTPException(status_code=422, detail="Unsupported type. Use jpeg/png/webp")

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=422, detail="File too large (max 10 MB)")
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="Empty file")

    ext = file.content_type.split("/")[-1].replace("jpeg", "jpg")
    key = f"user-uploads/{current_user.id}/{uuid.uuid4()}.{ext}"

    upload_file(storage_settings.r2_bucket_uploads, key, data, file.content_type)

    url = get_signed_url(storage_settings.r2_bucket_uploads, key, expires=604800)
    return {"url": url}
