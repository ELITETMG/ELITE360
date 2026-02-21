import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access, require_role
from app.models.models import (
    Inspection, InspectionTemplate, InspectionStatus,
    Task, TaskStatus, User, AuditLog, Project
)
from app.schemas.schemas import (
    InspectionTemplateCreate, InspectionTemplateResponse,
    InspectionCreate, InspectionUpdate, InspectionResponse
)

router = APIRouter(prefix="/api", tags=["inspections"])


def _inspection_to_response(insp: Inspection) -> InspectionResponse:
    return InspectionResponse(
        id=insp.id,
        task_id=insp.task_id,
        template_id=insp.template_id,
        inspector_id=insp.inspector_id,
        inspector_name=insp.inspector.full_name if insp.inspector else None,
        status=insp.status.value,
        checklist_results=insp.checklist_results,
        comments=insp.comments,
        template_name=insp.template.name if insp.template else None,
        checklist_items=insp.template.checklist_items if insp.template else None,
        created_at=insp.created_at,
        updated_at=insp.updated_at
    )


@router.get("/inspection-templates", response_model=list[InspectionTemplateResponse])
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    templates = db.query(InspectionTemplate).order_by(InspectionTemplate.created_at.desc()).all()
    return [InspectionTemplateResponse(
        id=t.id, name=t.name, task_type_id=t.task_type_id,
        checklist_items=t.checklist_items, require_photos=t.require_photos,
        created_at=t.created_at
    ) for t in templates]


@router.post("/inspection-templates", response_model=InspectionTemplateResponse)
def create_template(
    data: InspectionTemplateCreate,
    user: User = Depends(require_role(["org_admin", "pm"])),
    db: Session = Depends(get_db)
):
    tmpl = InspectionTemplate(
        name=data.name,
        task_type_id=data.task_type_id,
        checklist_items=data.checklist_items,
        require_photos=data.require_photos
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return InspectionTemplateResponse(
        id=tmpl.id, name=tmpl.name, task_type_id=tmpl.task_type_id,
        checklist_items=tmpl.checklist_items, require_photos=tmpl.require_photos,
        created_at=tmpl.created_at
    )


@router.post("/tasks/{task_id}/inspections", response_model=InspectionResponse)
def create_inspection(
    task_id: str,
    data: InspectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    insp = Inspection(
        task_id=task_id,
        template_id=data.template_id,
        inspector_id=user.id,
        status=InspectionStatus.PENDING,
        comments=data.comments
    )
    db.add(insp)
    db.add(AuditLog(
        user_id=user.id, action="create_inspection",
        entity_type="task", entity_id=task_id,
        details=f"inspection created"
    ))
    db.commit()
    db.refresh(insp)
    return _inspection_to_response(insp)


@router.get("/tasks/{task_id}/inspections", response_model=list[InspectionResponse])
def list_inspections(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    inspections = db.query(Inspection).filter(
        Inspection.task_id == task_id
    ).order_by(Inspection.created_at.desc()).all()
    return [_inspection_to_response(i) for i in inspections]


@router.put("/inspections/{inspection_id}", response_model=InspectionResponse)
def update_inspection(
    inspection_id: str,
    data: InspectionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    insp = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if data.checklist_results is not None:
        insp.checklist_results = data.checklist_results
    if data.comments is not None:
        insp.comments = data.comments
    if data.status is not None:
        try:
            insp.status = InspectionStatus(data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid inspection status")

    db.commit()
    db.refresh(insp)
    return _inspection_to_response(insp)


@router.post("/inspections/{inspection_id}/approve", response_model=InspectionResponse)
def approve_inspection(
    inspection_id: str,
    user: User = Depends(require_role(["inspector", "pm", "org_admin"])),
    db: Session = Depends(get_db)
):
    insp = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    task = db.query(Task).filter(Task.id == insp.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    insp.status = InspectionStatus.PASSED

    if task:
        task.status = TaskStatus.APPROVED

    db.add(AuditLog(
        user_id=user.id, action="approve_inspection",
        entity_type="task", entity_id=insp.task_id,
        details=f"inspection {inspection_id} approved, task status set to approved"
    ))
    db.commit()
    db.refresh(insp)
    return _inspection_to_response(insp)


@router.post("/inspections/{inspection_id}/reject", response_model=InspectionResponse)
def reject_inspection(
    inspection_id: str,
    data: InspectionUpdate = None,
    user: User = Depends(require_role(["inspector", "pm", "org_admin"])),
    db: Session = Depends(get_db)
):
    insp = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    task = db.query(Task).filter(Task.id == insp.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    insp.status = InspectionStatus.FAILED
    if data and data.comments:
        insp.comments = data.comments

    if task:
        task.status = TaskStatus.REWORK

    reject_details = f"inspection {inspection_id} rejected, task status set to rework"
    if data and data.comments:
        reject_details += f", reason: {data.comments}"

    db.add(AuditLog(
        user_id=user.id, action="reject_inspection",
        entity_type="task", entity_id=insp.task_id,
        details=reject_details
    ))
    db.commit()
    db.refresh(insp)
    return _inspection_to_response(insp)


@router.get("/inspections/pending", response_model=list[InspectionResponse])
def list_pending_inspections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    inspections = db.query(Inspection).filter(
        Inspection.status.in_([InspectionStatus.PENDING, InspectionStatus.IN_PROGRESS])
    ).order_by(Inspection.created_at.desc()).all()
    return [_inspection_to_response(i) for i in inspections]
