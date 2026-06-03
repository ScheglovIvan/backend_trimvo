from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from models.category import Category
from schemas.template import CategoryOut

router = APIRouter(prefix="/v1/categories", tags=["categories"])


@router.get("", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return [
        CategoryOut.model_validate(c)
        for c in db.query(Category).order_by(Category.order).all()
    ]
