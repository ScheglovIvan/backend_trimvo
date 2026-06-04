from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from core.database import get_db
from core.dependencies import get_admin_user
from models.template import Template
from models.category import CategoryTemplate
from models.user import User
from models.admin_config import AuditLog
from schemas.template import TemplateListResponse
from services import storage
from services.queue import publish, QUEUE_THUMBNAIL

router = APIRouter(prefix="/v1/admin/templates", tags=["admin-templates"])


def _audit(db, user_id, action, entity_id, details=None):
    log = AuditLog(user_id=user_id, action=action, entity="template",
                   entity_id=str(entity_id), details=details or {})
    db.add(log)


def _public_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    clean_path = path.lstrip("/")
    return f"{storage.settings.r2_public_url_templates}/{clean_path}"


def _to_dict(t: Template) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "status": t.status or "ready",
        "thumb_url": _public_url(t.thumb_path),
        "preview_url": _public_url(t.preview_path),
        "preview_compressed_url": _public_url(t.preview_compressed_path),
        "gif_url": _public_url(t.gif_path),
        "video_url": _public_url(t.video_path),
        "likes": t.likes,
        "plays": t.plays,
        "is_active": t.is_active,
        "gems_cost": t.gems_cost if t.gems_cost is not None else 200,
        "photo_slots": t.photo_slots if t.photo_slots is not None else 1,
        "has_male_slot": t.has_male_slot or False,
        "has_female_slot": t.has_female_slot or False,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "created_by": str(t.created_by) if t.created_by else None,
    }


def _enqueue_thumbnail(template_id: str, skip_thumb: bool = False):
    try:
        publish(QUEUE_THUMBNAIL, {"template_id": template_id, "skip_thumb": skip_thumb})
    except Exception as e:
        print(f"Failed to enqueue thumbnail job for {template_id}: {e}")


@router.get("")
def list_templates(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    query = db.query(Template)
    if search:
        query = query.filter(Template.title.ilike(f"%{search}%"))
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [_to_dict(t) for t in items], "total": total}


@router.post("")
async def create_template(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    likes: int = Form(0),
    plays: int = Form(0),
    gems_cost: int = Form(200),
    photo_slots: int = Form(1),
    has_male_slot: bool = Form(False),
    has_female_slot: bool = Form(False),
    video: Optional[UploadFile] = File(None),
    thumb: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    t = Template(
        title=title,
        description=description,
        likes=likes,
        plays=plays,
        gems_cost=gems_cost,
        photo_slots=photo_slots,
        has_male_slot=has_male_slot,
        has_female_slot=has_female_slot,
        created_by=admin.id,
        status="ready",
    )
    db.add(t)
    db.flush()

    bucket = storage.settings.r2_bucket_templates
    base_key = f"templates/{t.id}"

    if thumb:
        data = await thumb.read()
        thumb_key = f"{base_key}/thumb_custom.jpg"
        storage.upload_file(bucket, thumb_key, data, thumb.content_type or "image/jpeg")
        t.thumb_path = thumb_key

    if video:
        data = await video.read()
        video_key = f"{base_key}/original.mp4"
        storage.upload_file(bucket, video_key, data, video.content_type or "video/mp4")
        t.video_path = video_key
        t.status = "processing"
        db.commit()
        db.refresh(t)
        _enqueue_thumbnail(str(t.id), skip_thumb=bool(t.thumb_path))
    else:
        db.commit()
        db.refresh(t)

    _audit(db, admin.id, "create", t.id, {"title": title})
    db.commit()
    return _to_dict(t)


@router.put("/{template_id}")
async def update_template(
    template_id: UUID,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_active: Optional[str] = Form(None),
    likes: Optional[int] = Form(None),
    plays: Optional[int] = Form(None),
    gems_cost: Optional[int] = Form(None),
    photo_slots: Optional[int] = Form(None),
    has_male_slot: Optional[str] = Form(None),
    has_female_slot: Optional[str] = Form(None),
    video: Optional[UploadFile] = File(None),
    thumb: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Not found")

    if title is not None:
        t.title = title
    if description is not None:
        t.description = description
    if is_active is not None:
        t.is_active = is_active.lower() in ("true", "1", "yes")
    if likes is not None:
        t.likes = likes
    if plays is not None:
        t.plays = plays
    if gems_cost is not None:
        t.gems_cost = gems_cost
    if photo_slots is not None:
        t.photo_slots = photo_slots
    if has_male_slot is not None:
        t.has_male_slot = has_male_slot.lower() in ("true", "1", "yes")
    if has_female_slot is not None:
        t.has_female_slot = has_female_slot.lower() in ("true", "1", "yes")

    bucket = storage.settings.r2_bucket_templates
    base_key = f"templates/{t.id}"

    if thumb:
        data = await thumb.read()
        thumb_key = f"{base_key}/thumb_custom.jpg"
        storage.upload_file(bucket, thumb_key, data, thumb.content_type or "image/jpeg")
        t.thumb_path = thumb_key

    if video:
        data = await video.read()
        video_key = f"{base_key}/original.mp4"
        storage.upload_file(bucket, video_key, data, video.content_type or "video/mp4")
        t.video_path = video_key
        t.status = "processing"
        db.commit()
        db.refresh(t)
        _enqueue_thumbnail(str(t.id), skip_thumb=bool(t.thumb_path))
    else:
        db.commit()
        db.refresh(t)

    _audit(db, admin.id, "update", template_id, {"title": title})
    db.commit()
    return _to_dict(t)


@router.post("/reprocess-compressed")
def reprocess_compressed(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    """Create preview_small.mp4 for all templates that don't have it yet"""
    templates = db.query(Template).filter(
        Template.video_path.isnot(None),
        Template.preview_compressed_path.is_(None),
    ).all()
    count = 0
    for t in templates:
        _enqueue_thumbnail(str(t.id))
        count += 1
    db.commit()
    return {"queued": count}


@router.post("/reprocess-all")
def reprocess_all(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    templates = db.query(Template).filter(
        Template.video_path.isnot(None),
        Template.thumb_path.is_(None),
    ).all()
    count = 0
    for t in templates:
        t.status = "queued"
        _enqueue_thumbnail(str(t.id))
        count += 1
    db.commit()
    return {"queued": count}


@router.post("/{template_id}/reprocess")
def reprocess_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    if not t.video_path:
        raise HTTPException(status_code=400, detail="No video uploaded")
    t.status = "queued"
    db.commit()
    _enqueue_thumbnail(str(t.id))
    return {"success": True, "status": "queued"}


@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    db.query(CategoryTemplate).filter(CategoryTemplate.template_id == template_id).delete()
    db.delete(t)
    _audit(db, admin.id, "delete", template_id)
    db.commit()
    return {"success": True}
