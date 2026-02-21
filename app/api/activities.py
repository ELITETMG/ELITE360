from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import Activity, Project, User
from app.schemas.schemas import ActivityResponse

router = APIRouter(prefix="/api", tags=["activities"])

@router.get("/projects/{project_id}/activities", response_model=list[ActivityResponse])
def list_activities(
    project_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    entity_type: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    q = db.query(Activity).filter(Activity.project_id == project_id)
    if entity_type:
        q = q.filter(Activity.entity_type == entity_type)
    activities = q.order_by(Activity.created_at.desc()).offset(offset).limit(limit).all()
    
    result = []
    for a in activities:
        u = db.query(User).filter(User.id == a.user_id).first() if a.user_id else None
        result.append(ActivityResponse(
            id=a.id, project_id=a.project_id, user_id=a.user_id,
            user_name=u.full_name if u else None,
            action=a.action, entity_type=a.entity_type,
            entity_id=a.entity_id, entity_name=a.entity_name,
            details=a.details, created_at=a.created_at
        ))
    return result

@router.get("/activities/recent", response_model=list[ActivityResponse])
def recent_activities(
    limit: int = Query(20, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.models import OrgMember
    memberships = db.query(OrgMember).filter(OrgMember.user_id == user.id).all()
    org_ids = [m.org_id for m in memberships]
    
    project_ids = []
    projects = db.query(Project).filter(
        (Project.executing_org_id.in_(org_ids)) | (Project.owner_org_id.in_(org_ids))
    ).all()
    project_ids = [p.id for p in projects]
    
    activities = db.query(Activity).filter(
        Activity.project_id.in_(project_ids)
    ).order_by(Activity.created_at.desc()).limit(limit).all()
    
    result = []
    for a in activities:
        u = db.query(User).filter(User.id == a.user_id).first() if a.user_id else None
        result.append(ActivityResponse(
            id=a.id, project_id=a.project_id, user_id=a.user_id,
            user_name=u.full_name if u else None,
            action=a.action, entity_type=a.entity_type,
            entity_id=a.entity_id, entity_name=a.entity_name,
            details=a.details, created_at=a.created_at
        ))
    return result
