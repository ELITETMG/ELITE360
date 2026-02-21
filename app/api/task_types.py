from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import TaskType, User, AuditLog
from app.schemas.schemas import TaskTypeCreate, TaskTypeResponse

router = APIRouter(prefix="/api/task-types", tags=["task-types"])


@router.get("", response_model=list[TaskTypeResponse])
def list_task_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(TaskType).order_by(TaskType.name).all()


@router.post("", response_model=TaskTypeResponse)
def create_task_type(data: TaskTypeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tt = TaskType(name=data.name, description=data.description, unit=data.unit, color=data.color)
    db.add(tt)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="task_type", entity_id=tt.id))
    db.commit()
    db.refresh(tt)
    return tt


@router.get("/{tt_id}", response_model=TaskTypeResponse)
def get_task_type(tt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tt = db.query(TaskType).filter(TaskType.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Task type not found")
    return tt


@router.delete("/{tt_id}")
def delete_task_type(tt_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tt = db.query(TaskType).filter(TaskType.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Task type not found")
    db.delete(tt)
    db.commit()
    return {"ok": True}
