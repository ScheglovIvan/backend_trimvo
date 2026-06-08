import uuid
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from core.database import get_db
from core.dependencies import get_current_user
from core.config import get_settings
from models.job import Job
from models.user import User
from models.template import Template
from models.admin_config import AdminConfig
from schemas.job import (
    JobCreate, JobCreateResponse, JobStatusResponse, JobOut, JobListResponse,
    CustomJobParams, CUSTOM_JOB_COST, ALLOWED_RESOLUTIONS, ALLOWED_QUALITIES, ALLOWED_FORMATS,
)
from services.queue import publish_job, QUEUE_GENERATOR
from services.gems import apply_svip_discount, deduct_gems, refund_gems
from services.storage import upload_file, settings as storage_settings, get_client

_settings = get_settings()


def _to_public_url(url: Optional[str]) -> Optional[str]:
    """Convert an expired presigned R2 URL to a stable public URL."""
    if not url or "X-Amz-" not in url:
        return url
    parsed = urlparse(url)
    parts = parsed.path.lstrip("/").split("/", 1)
    if len(parts) < 2 or not _settings.r2_public_url_results:
        return url
    key = parts[1]  # strip bucket prefix, keep job_id/image_n.png
    return f"{_settings.r2_public_url_results.rstrip('/')}/{key}"

PHOTO_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
PHOTO_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse)
def create_job(
    body: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, 'is_banned', False):
        raise HTTPException(status_code=403, detail="Account is banned")

    template = db.query(Template).filter(
        Template.id == body.template_id,
        Template.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    quality = 'standard'
    duration_seconds = 5

    if template.gems_cost and template.gems_cost > 0:
        cost = template.gems_cost
    else:
        cost = 200

    cost = apply_svip_discount(cost, current_user)

    deduct_gems(
        db,
        current_user,
        cost,
        description=f"Video generation: template '{template.title}' ({quality}, {duration_seconds}s)",
        reference_id=None,
    )

    job = Job(
        user_id=current_user.id,
        template_id=body.template_id,
        options=body.options.model_dump() if body.options else {},
        gems_cost=cost,
        quality=quality,
        duration_seconds=duration_seconds,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_job(str(job.id))
    except Exception as e:
        refund_gems(db, current_user, cost, str(job.id))
        job.status = "failed"
        job.error = f"Queue error: {str(e)}"
        db.commit()

    return JobCreateResponse(job_id=job.id, status=job.status, gems_cost=cost)


def _get_custom_cost(db: Session, quality: str) -> int:
    key = f"CUSTOM_JOB_COST_{quality.upper()}"
    row = db.query(AdminConfig).filter(AdminConfig.key == key).first()
    if row:
        try:
            return int(row.value)
        except (ValueError, TypeError):
            pass
    return CUSTOM_JOB_COST.get(quality, 300)


IMAGE_JOB_ALLOWED_ASPECTS = {"1:1", "3:4", "4:3", "16:9", "9:16"}
IMAGE_JOB_DEFAULT_COST = 150


def _get_image_cost(db: Session) -> int:
    row = db.query(AdminConfig).filter(AdminConfig.key == "IMAGE_JOB_COST").first()
    if row:
        try:
            return int(row.value)
        except (ValueError, TypeError):
            pass
    return IMAGE_JOB_DEFAULT_COST


async def _read_and_validate_photo(photo: UploadFile, field: str) -> bytes:
    if photo.content_type not in PHOTO_ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"{field}: unsupported type '{photo.content_type}'. Allowed: jpeg, png, webp",
        )
    data = await photo.read()
    if len(data) > PHOTO_MAX_BYTES:
        raise HTTPException(status_code=422, detail=f"{field}: file too large (max 10 MB)")
    if len(data) == 0:
        raise HTTPException(status_code=422, detail=f"{field}: empty file")
    return data


@router.post("/custom", response_model=JobCreateResponse)
async def create_custom_job(
    photo_1: UploadFile = File(..., description="First photo (jpeg/png/webp, max 10 MB)"),
    photo_2: Optional[UploadFile] = File(None, description="Second photo (optional)"),
    prompt: str = Form(..., min_length=1, max_length=2000),
    resolution: str = Form("1080x1920"),
    quality: str = Form("standard"),
    format: str = Form("mp4"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, 'is_banned', False):
        raise HTTPException(status_code=403, detail="Account is banned")

    try:
        CustomJobParams(prompt=prompt, resolution=resolution, quality=quality, format=format)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    photo_1_bytes = await _read_and_validate_photo(photo_1, "photo_1")
    photo_2_bytes: Optional[bytes] = None
    if photo_2 and photo_2.filename:
        photo_2_bytes = await _read_and_validate_photo(photo_2, "photo_2")

    cost = _get_custom_cost(db, quality)
    cost = apply_svip_discount(cost, current_user)

    job_id = uuid.uuid4()

    ext_1 = photo_1.content_type.split("/")[-1].replace("jpeg", "jpg")
    photo_1_key = f"custom/{job_id}/photo_1.{ext_1}"
    upload_file(storage_settings.r2_bucket_uploads, photo_1_key, photo_1_bytes, photo_1.content_type)

    photo_2_key: Optional[str] = None
    if photo_2_bytes is not None:
        ext_2 = photo_2.content_type.split("/")[-1].replace("jpeg", "jpg")
        photo_2_key = f"custom/{job_id}/photo_2.{ext_2}"
        upload_file(storage_settings.r2_bucket_uploads, photo_2_key, photo_2_bytes, photo_2.content_type)

    deduct_gems(
        db,
        current_user,
        cost,
        description=f"Custom video generation ({quality}, {resolution}, {format})",
        reference_id=None,
    )

    options = {
        "prompt": prompt,
        "resolution": resolution,
        "format": format,
        "photo_1_path": photo_1_key,
    }
    if photo_2_key:
        options["photo_2_path"] = photo_2_key

    job = Job(
        id=job_id,
        user_id=current_user.id,
        template_id=None,
        job_type="custom",
        options=options,
        gems_cost=cost,
        quality=quality,
        duration_seconds=10,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_job(str(job.id))
    except Exception as e:
        refund_gems(db, current_user, cost, str(job.id))
        job.status = "failed"
        job.error = f"Queue error: {str(e)}"
        db.commit()

    return JobCreateResponse(job_id=job.id, status=job.status, gems_cost=cost)


@router.post("/image", response_model=JobCreateResponse)
async def create_image_job(
    photo: UploadFile = File(..., description="Input photo (jpeg/png/webp, max 10 MB)"),
    prompt: str = Form(..., min_length=1, max_length=2000, description="Editing instruction, e.g. 'transform into a vampire'"),
    aspect_ratio: str = Form("1:1", description="1:1, 3:4, 4:3, 16:9, 9:16"),
    count: int = Form(1, ge=1, le=4, description="Number of variants to generate (1–4)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, 'is_banned', False):
        raise HTTPException(status_code=403, detail="Account is banned")

    if aspect_ratio not in IMAGE_JOB_ALLOWED_ASPECTS:
        raise HTTPException(
            status_code=422,
            detail=f"aspect_ratio must be one of {sorted(IMAGE_JOB_ALLOWED_ASPECTS)}",
        )

    photo_bytes = await _read_and_validate_photo(photo, "photo")

    base_cost = _get_image_cost(db)
    base_cost = apply_svip_discount(base_cost, current_user)
    cost = base_cost * count

    job_id = uuid.uuid4()

    ext = photo.content_type.split("/")[-1].replace("jpeg", "jpg")
    photo_key = f"image/{job_id}/photo.{ext}"
    upload_file(storage_settings.r2_bucket_uploads, photo_key, photo_bytes, photo.content_type)

    deduct_gems(
        db,
        current_user,
        cost,
        description=f"Image generation x{count} ({aspect_ratio})",
        reference_id=None,
    )

    job = Job(
        id=job_id,
        user_id=current_user.id,
        template_id=None,
        job_type="image",
        options={
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "count": count,
            "photo_1_path": photo_key,
        },
        gems_cost=cost,
        quality="standard",
        duration_seconds=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_job(str(job.id), queue=QUEUE_GENERATOR)
    except Exception as e:
        refund_gems(db, current_user, cost, str(job.id))
        job.status = "failed"
        job.error = f"Queue error: {str(e)}"
        db.commit()

    return JobCreateResponse(job_id=job.id, status=job.status, gems_cost=cost)


@router.get("", response_model=JobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs = db.query(Job).filter(Job.user_id == current_user.id).all()
    return JobListResponse(items=[JobOut.model_validate(j) for j in jobs], total=len(jobs))


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete result files from R2 (best-effort, don't fail if missing)
    try:
        client = get_client()
        bucket = storage_settings.r2_bucket_results
        response = client.list_objects_v2(Bucket=bucket, Prefix=f"{job_id}/")
        for obj in response.get("Contents", []):
            try:
                client.delete_object(Bucket=bucket, Key=obj["Key"])
            except Exception:
                pass
    except Exception:
        pass

    db.delete(job)
    db.commit()


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result_urls_raw = (job.options or {}).get("result_image_urls") or None
    result_urls = [_to_public_url(u) for u in result_urls_raw] if result_urls_raw else None
    return JobStatusResponse(
        status=job.status,
        progress=job.progress,
        result_url=_to_public_url(job.result_path),
        preview_url=job.preview_url,
        thumb_url=job.thumb_url,
        original_url=job.original_url,
        result_urls=result_urls,
        error=job.error,
    )
