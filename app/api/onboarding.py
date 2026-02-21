from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    OnboardingWorkflowTemplate, OnboardingWorkflowStep,
    OnboardingWorkflowInstance, OnboardingWorkflowStepInstance,
    OrgMember, User
)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _get_user_org(db: Session, user: User):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No org membership")
    return membership.org_id


@router.get("/stats")
def get_onboarding_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    active_workflows = db.query(func.count(OnboardingWorkflowInstance.id)).filter(
        OnboardingWorkflowInstance.org_id == org_id,
        OnboardingWorkflowInstance.status == "active"
    ).scalar() or 0

    total_instances = db.query(func.count(OnboardingWorkflowInstance.id)).filter(
        OnboardingWorkflowInstance.org_id == org_id
    ).scalar() or 0

    completed_instances = db.query(func.count(OnboardingWorkflowInstance.id)).filter(
        OnboardingWorkflowInstance.org_id == org_id,
        OnboardingWorkflowInstance.status == "completed"
    ).scalar() or 0

    completion_rate = round((completed_instances / total_instances * 100), 1) if total_instances > 0 else 0

    completed_with_dates = db.query(OnboardingWorkflowInstance).filter(
        OnboardingWorkflowInstance.org_id == org_id,
        OnboardingWorkflowInstance.status == "completed",
        OnboardingWorkflowInstance.completed_date.isnot(None),
        OnboardingWorkflowInstance.start_date.isnot(None)
    ).all()

    if completed_with_dates:
        total_days = sum((inst.completed_date - inst.start_date).days for inst in completed_with_dates)
        avg_days = round(total_days / len(completed_with_dates), 1)
    else:
        avg_days = 0

    template_count = db.query(func.count(OnboardingWorkflowTemplate.id)).filter(
        OnboardingWorkflowTemplate.org_id == org_id,
        OnboardingWorkflowTemplate.is_active == True
    ).scalar() or 0

    pending_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).join(
        OnboardingWorkflowInstance,
        OnboardingWorkflowStepInstance.instance_id == OnboardingWorkflowInstance.id
    ).filter(
        OnboardingWorkflowInstance.org_id == org_id,
        OnboardingWorkflowInstance.status == "active",
        OnboardingWorkflowStepInstance.status == "pending"
    ).scalar() or 0

    return {
        "active_workflows": active_workflows,
        "total_instances": total_instances,
        "completed_instances": completed_instances,
        "completion_rate": completion_rate,
        "avg_days_to_complete": avg_days,
        "active_templates": template_count,
        "pending_steps": pending_steps,
    }


@router.get("/templates")
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    templates = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.org_id == org_id
    ).order_by(desc(OnboardingWorkflowTemplate.created_at)).all()

    result = []
    for t in templates:
        step_count = db.query(func.count(OnboardingWorkflowStep.id)).filter(
            OnboardingWorkflowStep.template_id == t.id
        ).scalar() or 0
        result.append({
            "id": t.id,
            "org_id": t.org_id,
            "name": t.name,
            "description": t.description,
            "role_type": t.role_type,
            "estimated_days": t.estimated_days,
            "is_active": t.is_active,
            "auto_assign_screening": t.auto_assign_screening,
            "auto_assign_drug_test": t.auto_assign_drug_test,
            "created_by": t.created_by,
            "creator_name": t.creator.full_name if t.creator else None,
            "step_count": step_count,
            "created_at": str(t.created_at) if t.created_at else None,
            "updated_at": str(t.updated_at) if t.updated_at else None,
        })
    return result


@router.post("/templates")
def create_template(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    template = OnboardingWorkflowTemplate(
        org_id=org_id,
        name=data["name"],
        description=data.get("description"),
        role_type=data.get("role_type"),
        estimated_days=int(data.get("estimated_days", 14)),
        is_active=data.get("is_active", True),
        auto_assign_screening=data.get("auto_assign_screening", True),
        auto_assign_drug_test=data.get("auto_assign_drug_test", True),
        created_by=user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": template.id, "name": template.name}


@router.get("/templates/{template_id}")
def get_template(template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    steps = db.query(OnboardingWorkflowStep).filter(
        OnboardingWorkflowStep.template_id == t.id
    ).order_by(OnboardingWorkflowStep.step_number).all()

    return {
        "id": t.id,
        "org_id": t.org_id,
        "name": t.name,
        "description": t.description,
        "role_type": t.role_type,
        "estimated_days": t.estimated_days,
        "is_active": t.is_active,
        "auto_assign_screening": t.auto_assign_screening,
        "auto_assign_drug_test": t.auto_assign_drug_test,
        "created_by": t.created_by,
        "creator_name": t.creator.full_name if t.creator else None,
        "created_at": str(t.created_at) if t.created_at else None,
        "updated_at": str(t.updated_at) if t.updated_at else None,
        "steps": [{
            "id": s.id,
            "step_number": s.step_number,
            "title": s.title,
            "description": s.description,
            "step_type": s.step_type,
            "is_required": s.is_required,
            "auto_trigger": s.auto_trigger,
            "trigger_action": s.trigger_action,
            "due_days_offset": s.due_days_offset,
            "assigned_role": s.assigned_role,
            "documents_required": s.documents_required,
            "created_at": str(s.created_at) if s.created_at else None,
        } for s in steps],
    }


@router.put("/templates/{template_id}")
def update_template(template_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    fields = ["name", "description", "role_type", "is_active",
              "auto_assign_screening", "auto_assign_drug_test"]
    for f in fields:
        if f in data:
            setattr(t, f, data[f])
    if "estimated_days" in data:
        t.estimated_days = int(data["estimated_days"])

    db.commit()
    db.refresh(t)
    return {"id": t.id, "name": t.name, "updated": True}


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(t)
    db.commit()
    return {"ok": True, "deleted": template_id}


@router.get("/templates/{template_id}/steps")
def list_steps(template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    steps = db.query(OnboardingWorkflowStep).filter(
        OnboardingWorkflowStep.template_id == template_id
    ).order_by(OnboardingWorkflowStep.step_number).all()

    return [{
        "id": s.id,
        "template_id": s.template_id,
        "step_number": s.step_number,
        "title": s.title,
        "description": s.description,
        "step_type": s.step_type,
        "is_required": s.is_required,
        "auto_trigger": s.auto_trigger,
        "trigger_action": s.trigger_action,
        "due_days_offset": s.due_days_offset,
        "assigned_role": s.assigned_role,
        "documents_required": s.documents_required,
        "created_at": str(s.created_at) if s.created_at else None,
    } for s in steps]


@router.post("/templates/{template_id}/steps")
def create_step(template_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    max_step = db.query(func.max(OnboardingWorkflowStep.step_number)).filter(
        OnboardingWorkflowStep.template_id == template_id
    ).scalar() or 0

    step = OnboardingWorkflowStep(
        template_id=template_id,
        step_number=data.get("step_number", max_step + 1),
        title=data["title"],
        description=data.get("description"),
        step_type=data.get("step_type", "task"),
        is_required=data.get("is_required", True),
        auto_trigger=data.get("auto_trigger", False),
        trigger_action=data.get("trigger_action"),
        due_days_offset=int(data.get("due_days_offset", 0)),
        assigned_role=data.get("assigned_role"),
        documents_required=data.get("documents_required"),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return {"id": step.id, "step_number": step.step_number, "title": step.title}


@router.put("/templates/{template_id}/steps/{step_id}")
def update_step(template_id: str, step_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    step = db.query(OnboardingWorkflowStep).filter(
        OnboardingWorkflowStep.id == step_id,
        OnboardingWorkflowStep.template_id == template_id
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    fields = ["title", "description", "step_type", "is_required", "auto_trigger",
              "trigger_action", "assigned_role", "documents_required"]
    for f in fields:
        if f in data:
            setattr(step, f, data[f])
    if "step_number" in data:
        step.step_number = int(data["step_number"])
    if "due_days_offset" in data:
        step.due_days_offset = int(data["due_days_offset"])

    db.commit()
    db.refresh(step)
    return {"id": step.id, "step_number": step.step_number, "title": step.title, "updated": True}


@router.delete("/templates/{template_id}/steps/{step_id}")
def delete_step(template_id: str, step_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    step = db.query(OnboardingWorkflowStep).filter(
        OnboardingWorkflowStep.id == step_id,
        OnboardingWorkflowStep.template_id == template_id
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    db.delete(step)
    db.commit()
    return {"ok": True, "deleted": step_id}


@router.put("/templates/{template_id}/steps/reorder")
def reorder_steps(template_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    t = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    step_order = data.get("step_ids", [])
    for idx, step_id in enumerate(step_order, start=1):
        step = db.query(OnboardingWorkflowStep).filter(
            OnboardingWorkflowStep.id == step_id,
            OnboardingWorkflowStep.template_id == template_id
        ).first()
        if step:
            step.step_number = idx

    db.commit()
    return {"ok": True, "reordered": len(step_order)}


@router.post("/launch")
def launch_workflow(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    template_id = data.get("template_id")
    new_hire_user_id = data.get("user_id")
    assigned_to = data.get("assigned_to")

    if not template_id or not new_hire_user_id:
        raise HTTPException(status_code=400, detail="template_id and user_id are required")

    template = db.query(OnboardingWorkflowTemplate).filter(
        OnboardingWorkflowTemplate.id == template_id,
        OnboardingWorkflowTemplate.org_id == org_id,
        OnboardingWorkflowTemplate.is_active == True
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Active template not found")

    hire_user = db.query(User).filter(User.id == new_hire_user_id).first()
    if not hire_user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    instance = OnboardingWorkflowInstance(
        org_id=org_id,
        template_id=template_id,
        user_id=new_hire_user_id,
        assigned_to=assigned_to or user.id,
        status="active",
        start_date=now,
        target_completion=now + timedelta(days=template.estimated_days),
        progress_pct=0,
        notes=data.get("notes"),
    )
    db.add(instance)
    db.flush()

    steps = db.query(OnboardingWorkflowStep).filter(
        OnboardingWorkflowStep.template_id == template_id
    ).order_by(OnboardingWorkflowStep.step_number).all()

    for step in steps:
        step_instance = OnboardingWorkflowStepInstance(
            instance_id=instance.id,
            step_id=step.id,
            status="pending",
            assigned_to=assigned_to or user.id,
        )
        db.add(step_instance)

    db.commit()
    db.refresh(instance)

    return {
        "id": instance.id,
        "template_id": instance.template_id,
        "user_id": instance.user_id,
        "status": instance.status,
        "start_date": str(instance.start_date),
        "target_completion": str(instance.target_completion) if instance.target_completion else None,
        "steps_created": len(steps),
    }


@router.get("/instances")
def list_instances(
    status: str = Query(None),
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(OnboardingWorkflowInstance).filter(
        OnboardingWorkflowInstance.org_id == org_id
    )
    if status:
        q = q.filter(OnboardingWorkflowInstance.status == status)
    if user_id:
        q = q.filter(OnboardingWorkflowInstance.user_id == user_id)

    instances = q.order_by(desc(OnboardingWorkflowInstance.created_at)).all()

    result = []
    for inst in instances:
        total_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
            OnboardingWorkflowStepInstance.instance_id == inst.id
        ).scalar() or 0
        completed_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
            OnboardingWorkflowStepInstance.instance_id == inst.id,
            OnboardingWorkflowStepInstance.status == "completed"
        ).scalar() or 0

        result.append({
            "id": inst.id,
            "org_id": inst.org_id,
            "template_id": inst.template_id,
            "template_name": inst.template.name if inst.template else None,
            "user_id": inst.user_id,
            "employee_name": inst.employee.full_name if inst.employee else None,
            "assigned_to": inst.assigned_to,
            "manager_name": inst.manager.full_name if inst.manager else None,
            "status": inst.status,
            "start_date": str(inst.start_date) if inst.start_date else None,
            "target_completion": str(inst.target_completion) if inst.target_completion else None,
            "completed_date": str(inst.completed_date) if inst.completed_date else None,
            "progress_pct": float(inst.progress_pct or 0),
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "notes": inst.notes,
            "created_at": str(inst.created_at) if inst.created_at else None,
        })
    return result


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    inst = db.query(OnboardingWorkflowInstance).filter(
        OnboardingWorkflowInstance.id == instance_id,
        OnboardingWorkflowInstance.org_id == org_id
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found")

    step_instances = db.query(OnboardingWorkflowStepInstance, OnboardingWorkflowStep).join(
        OnboardingWorkflowStep,
        OnboardingWorkflowStepInstance.step_id == OnboardingWorkflowStep.id
    ).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id
    ).order_by(OnboardingWorkflowStep.step_number).all()

    return {
        "id": inst.id,
        "org_id": inst.org_id,
        "template_id": inst.template_id,
        "template_name": inst.template.name if inst.template else None,
        "user_id": inst.user_id,
        "employee_name": inst.employee.full_name if inst.employee else None,
        "assigned_to": inst.assigned_to,
        "manager_name": inst.manager.full_name if inst.manager else None,
        "status": inst.status,
        "start_date": str(inst.start_date) if inst.start_date else None,
        "target_completion": str(inst.target_completion) if inst.target_completion else None,
        "completed_date": str(inst.completed_date) if inst.completed_date else None,
        "progress_pct": float(inst.progress_pct or 0),
        "notes": inst.notes,
        "created_at": str(inst.created_at) if inst.created_at else None,
        "updated_at": str(inst.updated_at) if inst.updated_at else None,
        "steps": [{
            "id": si.id,
            "step_id": si.step_id,
            "step_number": step.step_number,
            "title": step.title,
            "description": step.description,
            "step_type": step.step_type,
            "is_required": step.is_required,
            "status": si.status,
            "assigned_to": si.assigned_to,
            "assignee_name": si.assignee.full_name if si.assignee else None,
            "started_at": str(si.started_at) if si.started_at else None,
            "completed_at": str(si.completed_at) if si.completed_at else None,
            "completed_by": si.completed_by,
            "completer_name": si.completer.full_name if si.completer else None,
            "notes": si.notes,
            "documents_uploaded": si.documents_uploaded,
            "due_days_offset": step.due_days_offset,
            "assigned_role": step.assigned_role,
        } for si, step in step_instances],
    }


@router.post("/instances/{instance_id}/steps/{step_id}/complete")
def complete_step(instance_id: str, step_id: str, data: dict = Body(default={}), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    inst = db.query(OnboardingWorkflowInstance).filter(
        OnboardingWorkflowInstance.id == instance_id,
        OnboardingWorkflowInstance.org_id == org_id
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found")

    step_inst = db.query(OnboardingWorkflowStepInstance).filter(
        OnboardingWorkflowStepInstance.id == step_id,
        OnboardingWorkflowStepInstance.instance_id == instance_id
    ).first()
    if not step_inst:
        raise HTTPException(status_code=404, detail="Step instance not found")

    step_inst.status = "completed"
    step_inst.completed_at = datetime.utcnow()
    step_inst.completed_by = user.id
    if data.get("notes"):
        step_inst.notes = data["notes"]
    if data.get("documents_uploaded"):
        step_inst.documents_uploaded = data["documents_uploaded"]

    total_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id
    ).scalar() or 1
    completed_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id,
        OnboardingWorkflowStepInstance.status == "completed"
    ).scalar() or 0

    inst.progress_pct = round((completed_steps / total_steps) * 100, 1)

    if completed_steps >= total_steps:
        inst.status = "completed"
        inst.completed_date = datetime.utcnow()

    db.commit()
    return {
        "ok": True,
        "step_id": step_id,
        "status": "completed",
        "progress_pct": inst.progress_pct,
        "workflow_status": inst.status,
        "completed_steps": completed_steps,
        "total_steps": total_steps,
    }


@router.get("/instances/{instance_id}/progress")
def get_progress(instance_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    inst = db.query(OnboardingWorkflowInstance).filter(
        OnboardingWorkflowInstance.id == instance_id,
        OnboardingWorkflowInstance.org_id == org_id
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow instance not found")

    total_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id
    ).scalar() or 0
    completed_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id,
        OnboardingWorkflowStepInstance.status == "completed"
    ).scalar() or 0
    in_progress_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id,
        OnboardingWorkflowStepInstance.status == "in_progress"
    ).scalar() or 0
    pending_steps = db.query(func.count(OnboardingWorkflowStepInstance.id)).filter(
        OnboardingWorkflowStepInstance.instance_id == instance_id,
        OnboardingWorkflowStepInstance.status == "pending"
    ).scalar() or 0

    days_elapsed = (datetime.utcnow() - inst.start_date).days if inst.start_date else 0
    days_remaining = None
    if inst.target_completion:
        days_remaining = max((inst.target_completion - datetime.utcnow()).days, 0)

    return {
        "instance_id": instance_id,
        "status": inst.status,
        "progress_pct": float(inst.progress_pct or 0),
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "in_progress_steps": in_progress_steps,
        "pending_steps": pending_steps,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "start_date": str(inst.start_date) if inst.start_date else None,
        "target_completion": str(inst.target_completion) if inst.target_completion else None,
        "completed_date": str(inst.completed_date) if inst.completed_date else None,
        "employee_name": inst.employee.full_name if inst.employee else None,
        "template_name": inst.template.name if inst.template else None,
    }
