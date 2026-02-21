from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.core.auth import get_current_user, require_org_membership, require_project_access, get_user_org_ids
from app.models.models import Project, Task, TaskStatus, User, OrgMember, AuditLog
from app.schemas.schemas import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_response(p, db):
    task_count = db.query(func.count(Task.id)).filter(Task.project_id == p.id).scalar()
    completed = db.query(func.count(Task.id)).filter(
        Task.project_id == p.id,
        Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED])
    ).scalar()
    org_name = p.executing_org.name if p.executing_org else None
    return ProjectResponse(
        id=p.id, name=p.name, description=p.description,
        status=p.status.value, executing_org_id=p.executing_org_id,
        owner_org_id=p.owner_org_id, executing_org_name=org_name,
        created_at=p.created_at, updated_at=p.updated_at,
        task_count=task_count, completed_count=completed
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    status: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_ids = get_user_org_ids(user)
    q = db.query(Project).filter(
        (Project.executing_org_id.in_(org_ids)) | (Project.owner_org_id.in_(org_ids))
    )
    if status:
        q = q.filter(Project.status == status)
    projects = q.order_by(Project.updated_at.desc()).all()
    return [_project_response(p, db) for p in projects]


@router.post("", response_model=ProjectResponse)
def create_project(
    data: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_org_membership(user, data.executing_org_id)
    project = Project(
        name=data.name, description=data.description,
        executing_org_id=data.executing_org_id,
        owner_org_id=data.owner_org_id
    )
    db.add(project)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="project", entity_id=project.id))
    db.commit()
    db.refresh(project)
    return _project_response(project, db)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    return _project_response(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str, data: ProjectUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.status is not None:
        valid = [s.value for s in TaskStatus.__class__.__mro__[0].__subclasses__()]
        project.status = data.status
    db.add(AuditLog(user_id=user.id, action="update", entity_type="project", entity_id=project.id))
    db.commit()
    db.refresh(project)
    return _project_response(project, db)
