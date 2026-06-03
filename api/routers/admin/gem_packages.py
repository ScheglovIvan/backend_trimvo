from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from core.database import get_db
from core.dependencies import get_admin_user
from models.gem_package import GemPackage
from schemas.gem_package import GemPackageCreate, GemPackageUpdate, GemPackageOut, GemPackageListResponse

router = APIRouter(prefix="/v1/admin/gem-packages", tags=["admin-gem-packages"])


@router.get("", response_model=GemPackageListResponse)
def list_packages(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    items = db.query(GemPackage).order_by(GemPackage.order).all()
    return GemPackageListResponse(items=[GemPackageOut.model_validate(p) for p in items])


@router.post("", response_model=GemPackageOut)
def create_package(body: GemPackageCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    pkg = GemPackage(**body.model_dump())
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return GemPackageOut.model_validate(pkg)


@router.put("/{pkg_id}", response_model=GemPackageOut)
def update_package(pkg_id: UUID, body: GemPackageUpdate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    pkg = db.query(GemPackage).filter(GemPackage.id == pkg_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(pkg, field, val)
    db.commit()
    db.refresh(pkg)
    return GemPackageOut.model_validate(pkg)


@router.delete("/{pkg_id}")
def delete_package(pkg_id: UUID, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    pkg = db.query(GemPackage).filter(GemPackage.id == pkg_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(pkg)
    db.commit()
    return {"success": True}
