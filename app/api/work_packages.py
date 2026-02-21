from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import WorkPackage, User, AuditLog
from app.schemas.schemas import WorkPackageCreate, WorkPackageResponse

router = APIRouter(prefix="/api/work-packages", tags=["work-packages"])


@router.get("", response_model=list[WorkPackageResponse])
def list_work_packages(project_id: str = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(WorkPackage)
    if project_id:
        q = q.filter(WorkPackage.project_id == project_id)
    return q.order_by(WorkPackage.created_at.desc()).all()


@router.post("", response_model=WorkPackageResponse)
def create_work_package(data: WorkPackageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wp = WorkPackage(name=data.name, description=data.description, project_id=data.project_id)
    db.add(wp)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="work_package", entity_id=wp.id))
    db.commit()
    db.refresh(wp)
    return wp


@router.get("/{wp_id}", response_model=WorkPackageResponse)
def get_work_package(wp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wp = db.query(WorkPackage).filter(WorkPackage.id == wp_id).first()
    if not wp:
        raise HTTPException(status_code=404, detail="Work package not found")
    return wp


@router.delete("/{wp_id}")
def delete_work_package(wp_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wp = db.query(WorkPackage).filter(WorkPackage.id == wp_id).first()
    if not wp:
        raise HTTPException(status_code=404, detail="Work package not found")
    db.delete(wp)
    db.commit()
    return {"ok": True}
