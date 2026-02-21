import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import ProjectBudget, Project, Task, User, Activity
from app.schemas.schemas import ProjectBudgetCreate, ProjectBudgetResponse

router = APIRouter(prefix="/api", tags=["budget"])

@router.get("/projects/{project_id}/budget", response_model=ProjectBudgetResponse)
def get_budget(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    budget = db.query(ProjectBudget).filter(ProjectBudget.project_id == project_id).first()
    if not budget:
        return ProjectBudgetResponse(
            id=None, project_id=project_id,
            total_budget=0, labor_budget=0, material_budget=0,
            contingency_pct=0, currency="USD",
            spent_to_date=0, remaining=0, created_at=None
        )
    
    spent = db.query(func.coalesce(func.sum(Task.actual_cost), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    
    return ProjectBudgetResponse(
        id=budget.id, project_id=budget.project_id,
        total_budget=(budget.total_budget or 0), labor_budget=(budget.labor_budget or 0),
        material_budget=(budget.material_budget or 0),
        contingency_pct=(budget.contingency_pct or 0), currency=budget.currency,
        spent_to_date=float(spent),
        remaining=(budget.total_budget or 0) - float(spent),
        created_at=budget.created_at
    )

@router.put("/projects/{project_id}/budget", response_model=ProjectBudgetResponse)
def update_budget(
    project_id: str,
    data: ProjectBudgetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    budget = db.query(ProjectBudget).filter(ProjectBudget.project_id == project_id).first()
    if not budget:
        budget = ProjectBudget(project_id=project_id)
        db.add(budget)
    
    budget.total_budget = data.total_budget
    budget.labor_budget = data.labor_budget
    budget.material_budget = data.material_budget
    budget.contingency_pct = data.contingency_pct
    budget.currency = data.currency
    
    activity = Activity(
        project_id=project_id, user_id=user.id,
        action="budget_updated", entity_type="budget",
        entity_id=budget.id, entity_name=f"Budget: ${data.total_budget:,.2f}"
    )
    db.add(activity)
    db.commit()
    db.refresh(budget)
    
    spent = db.query(func.coalesce(func.sum(Task.actual_cost), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    
    return ProjectBudgetResponse(
        id=budget.id, project_id=budget.project_id,
        total_budget=(budget.total_budget or 0), labor_budget=(budget.labor_budget or 0),
        material_budget=(budget.material_budget or 0),
        contingency_pct=(budget.contingency_pct or 0), currency=budget.currency,
        spent_to_date=float(spent),
        remaining=(budget.total_budget or 0) - float(spent),
        created_at=budget.created_at
    )

@router.get("/projects/{project_id}/cost-summary")
def cost_summary(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    from app.models.models import TaskStatus
    
    total_planned = db.query(func.coalesce(func.sum(Task.total_cost), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    total_actual = db.query(func.coalesce(func.sum(Task.actual_cost), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    
    by_status = db.query(
        Task.status,
        func.count(Task.id).label('count'),
        func.coalesce(func.sum(Task.total_cost), 0).label('planned_cost'),
        func.coalesce(func.sum(Task.actual_cost), 0).label('actual_cost')
    ).filter(Task.project_id == project_id).group_by(Task.status).all()
    
    from app.models.models import TaskType
    by_type = db.query(
        TaskType.name,
        func.count(Task.id).label('count'),
        func.coalesce(func.sum(Task.total_cost), 0).label('planned_cost'),
        func.coalesce(func.sum(Task.actual_cost), 0).label('actual_cost')
    ).join(TaskType, Task.task_type_id == TaskType.id).filter(
        Task.project_id == project_id
    ).group_by(TaskType.name).all()
    
    budget = db.query(ProjectBudget).filter(ProjectBudget.project_id == project_id).first()
    
    budget_amount = (budget.total_budget or 0) if budget else 0
    
    return {
        "total_planned_cost": float(total_planned),
        "total_actual_cost": float(total_actual),
        "variance": float(total_planned) - float(total_actual),
        "budget": budget_amount,
        "budget_remaining": (budget_amount - float(total_actual)) if budget_amount > 0 else 0,
        "budget_utilization_pct": (float(total_actual) / budget_amount * 100) if budget_amount > 0 else 0,
        "by_status": [
            {"status": str(s.status.value if hasattr(s.status, 'value') else s.status), "count": s.count, "planned_cost": float(s.planned_cost), "actual_cost": float(s.actual_cost)}
            for s in by_status
        ],
        "by_type": [
            {"type": s.name, "count": s.count, "planned_cost": float(s.planned_cost), "actual_cost": float(s.actual_cost)}
            for s in by_type
        ]
    }
