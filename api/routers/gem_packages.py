from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.gem_package import GemPackage
from schemas.gem_package import GemPackageOut, GemPackageListResponse

router = APIRouter(prefix="/v1/gem-packages", tags=["gem-packages"])


@router.get("", response_model=GemPackageListResponse)
def list_gem_packages(db: Session = Depends(get_db)):
    items = (
        db.query(GemPackage)
        .filter(GemPackage.is_active == True)
        .order_by(GemPackage.order)
        .all()
    )
    return GemPackageListResponse(items=[GemPackageOut.model_validate(p) for p in items])
