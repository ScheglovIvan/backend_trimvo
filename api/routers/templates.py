from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from core.config import get_settings
from core.database import get_db
from models.template import Template
from models.trend import Trend
from schemas.template import TemplateListResponse, TemplateDetail, TemplateOut
from services import storage

router = APIRouter(prefix="/v1/templates", tags=["templates"])

_settings = get_settings()


def _pub(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"{_settings.r2_public_url_templates}/{path.lstrip('/')}"


def _to_out(t: Template) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        title=t.title,
        description=t.description,
        thumb_url=_pub(t.thumb_path),
        preview_url=_pub(t.preview_path),
        preview_compressed_url=_pub(t.preview_compressed_path),
        gif_url=_pub(t.gif_path),
        likes=t.likes,
        plays=t.plays,
        is_active=t.is_active,
        created_at=t.created_at,
        gems_cost=t.gems_cost if t.gems_cost is not None else 200,
        photo_slots=t.photo_slots if t.photo_slots is not None else 1,
        has_male_slot=t.has_male_slot or False,
        has_female_slot=t.has_female_slot or False,
    )


def _to_detail(t: Template) -> TemplateDetail:
    return TemplateDetail(
        id=t.id,
        title=t.title,
        description=t.description,
        thumb_url=_pub(t.thumb_path),
        preview_url=_pub(t.preview_path),
        preview_compressed_url=_pub(t.preview_compressed_path),
        gif_url=_pub(t.gif_path),
        video_url=_pub(t.video_path),
        likes=t.likes,
        plays=t.plays,
        is_active=t.is_active,
        created_at=t.created_at,
        created_by=t.created_by,
        gems_cost=t.gems_cost if t.gems_cost is not None else 200,
        photo_slots=t.photo_slots if t.photo_slots is not None else 1,
        has_male_slot=t.has_male_slot or False,
        has_female_slot=t.has_female_slot or False,
    )


@router.get("", response_model=TemplateListResponse)
def list_templates(
    category: Optional[UUID] = None,
    trending: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Template).filter(Template.is_active == True)

    if trending:
        trend_ids = db.query(Trend.template_id).all()
        ids = [t[0] for t in trend_ids]
        query = query.filter(Template.id.in_(ids))

    if category:
        from models.category import CategoryTemplate

        cat_rows = db.query(CategoryTemplate).filter(
            CategoryTemplate.category_id == category
        ).order_by(CategoryTemplate.order).all()

        ordered_ids = [r.template_id for r in cat_rows]
        if not ordered_ids:
            return TemplateListResponse(items=[], total=0)

        order_map = {tid: idx for idx, tid in enumerate(ordered_ids)}
        query = query.filter(Template.id.in_(ordered_ids))
        total = query.count()
        items = query.all()
        items.sort(key=lambda t: order_map.get(t.id, 999))
        return TemplateListResponse(
            items=[_to_out(t) for t in items[(page - 1) * per_page: page * per_page]],
            total=total,
        )

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return TemplateListResponse(items=[_to_out(t) for t in items], total=total)


@router.get("/{template_id}", response_model=TemplateDetail)
def get_template(template_id: UUID, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    t = db.query(Template).filter(Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    t.plays += 1
    db.commit()
    return _to_detail(t)
