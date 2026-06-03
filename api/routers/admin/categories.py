from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from core.database import get_db
from core.dependencies import get_admin_user
from models.category import Category, CategoryTemplate
from models.template import Template
from schemas.template import CategoryOut, CategoryCreate, CategoryUpdate
from services import storage


def _public_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"{storage.settings.r2_public_url_templates}/{path.lstrip('/')}"

router = APIRouter(prefix="/v1/admin/categories", tags=["admin-categories"])


class AssignTemplatesBody(BaseModel):
    template_ids: List[UUID]


class UpdateTemplateOrderBody(BaseModel):
    order: int


@router.get("", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    return [CategoryOut.model_validate(c) for c in db.query(Category).order_by(Category.order).all()]


@router.post("", response_model=CategoryOut)
def create_category(body: CategoryCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    c = Category(name=body.name, order=body.order)
    db.add(c)
    db.commit()
    db.refresh(c)
    return CategoryOut.model_validate(c)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: UUID, body: CategoryUpdate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    c = db.query(Category).filter(Category.id == category_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return CategoryOut.model_validate(c)


@router.delete("/{category_id}")
def delete_category(category_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    c = db.query(Category).filter(Category.id == category_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(c)
    db.commit()
    return {"success": True}


@router.get("/{category_id}/templates")
def list_category_templates(
    category_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    c = db.query(Category).filter(Category.id == category_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    rows = (
        db.query(Template, CategoryTemplate.order)
        .join(CategoryTemplate, CategoryTemplate.template_id == Template.id)
        .filter(CategoryTemplate.category_id == category_id)
        .order_by(CategoryTemplate.order)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "description": t.description,
            "thumb_url": _public_url(t.thumb_path),
            "preview_url": _public_url(t.preview_path),
            "gif_url": _public_url(t.gif_path),
            "likes": t.likes,
            "plays": t.plays,
            "is_active": t.is_active,
            "order": order,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t, order in rows
    ]


@router.delete("/{category_id}/templates/{template_id}")
def remove_template_from_category(
    category_id: UUID,
    template_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    row = db.query(CategoryTemplate).filter(
        CategoryTemplate.category_id == category_id,
        CategoryTemplate.template_id == template_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not in category")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.patch("/{category_id}/templates/{template_id}/order")
def update_template_order(
    category_id: UUID,
    template_id: UUID,
    body: UpdateTemplateOrderBody,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    row = db.query(CategoryTemplate).filter(
        CategoryTemplate.category_id == category_id,
        CategoryTemplate.template_id == template_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Template not in category")
    row.order = body.order
    db.commit()
    return {"success": True}


@router.post("/{category_id}/templates")
def assign_templates(
    category_id: UUID,
    body: AssignTemplatesBody,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    c = db.query(Category).filter(Category.id == category_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    for i, tid in enumerate(body.template_ids):
        existing = db.query(CategoryTemplate).filter(
            CategoryTemplate.category_id == category_id,
            CategoryTemplate.template_id == tid,
        ).first()
        if not existing:
            db.add(CategoryTemplate(category_id=category_id, template_id=tid, order=i))
    db.commit()
    return {"success": True}
