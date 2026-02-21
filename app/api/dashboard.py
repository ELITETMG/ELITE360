from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import Project, Task, TaskStatus, User
from app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_ids = [m.org_id for m in user.memberships]
    projects = db.query(Project).filter(
        (Project.executing_org_id.in_(org_ids)) | (Project.owner_org_id.in_(org_ids))
    ).all()
    project_ids = [p.id for p in projects]

    total_tasks = db.query(func.count(Task.id)).filter(Task.project_id.in_(project_ids)).scalar() or 0
    completed = db.query(func.count(Task.id)).filter(
        Task.project_id.in_(project_ids),
        Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED])
    ).scalar() or 0
    in_progress = db.query(func.count(Task.id)).filter(
        Task.project_id.in_(project_ids),
        Task.status == TaskStatus.IN_PROGRESS
    ).scalar() or 0
    planned = db.query(func.coalesce(func.sum(Task.planned_qty), 0)).filter(
        Task.project_id.in_(project_ids)
    ).scalar()
    actual = db.query(func.coalesce(func.sum(Task.actual_qty), 0)).filter(
        Task.project_id.in_(project_ids)
    ).scalar()

    active_count = sum(1 for p in projects if p.status.value == "active")

    return DashboardStats(
        total_projects=len(projects), active_projects=active_count,
        total_tasks=total_tasks, completed_tasks=completed,
        in_progress_tasks=in_progress,
        total_planned_qty=float(planned), total_actual_qty=float(actual)
    )
