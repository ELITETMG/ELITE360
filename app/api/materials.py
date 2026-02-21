import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access, get_user_org_ids, get_user_role_in_org
from app.models.models import Material, TaskMaterial, Task, Project, User, Activity, OrgMember
from app.schemas.schemas import MaterialCreate, MaterialResponse, TaskMaterialCreate, TaskMaterialResponse

router = APIRouter(prefix="/api", tags=["materials"])

@router.get("/materials", response_model=list[MaterialResponse])
def list_materials(
    category: str = Query(None),
    low_stock: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = db.query(Material)
    if category:
        q = q.filter(Material.category == category)
    if low_stock:
        q = q.filter(Material.stock_qty <= Material.min_stock_qty)
    return [MaterialResponse(
        id=m.id, name=m.name, sku=m.sku, category=m.category,
        unit=m.unit, unit_cost=m.unit_cost, stock_qty=m.stock_qty,
        min_stock_qty=m.min_stock_qty, description=m.description,
        created_at=m.created_at
    ) for m in q.order_by(Material.name).all()]

@router.post("/materials", response_model=MaterialResponse, status_code=201)
def create_material(
    data: MaterialCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user has appropriate role in any organization
    user_orgs = get_user_org_ids(user)
    has_permission = False
    for org_id in user_orgs:
        role = get_user_role_in_org(user.id, org_id, db)
        if role in ["org_admin", "pm", "field_lead"]:
            has_permission = True
            break
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to create materials")
    
    mat = Material(
        name=data.name, sku=data.sku, category=data.category,
        unit=data.unit, unit_cost=data.unit_cost,
        stock_qty=data.stock_qty, min_stock_qty=data.min_stock_qty,
        description=data.description
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return MaterialResponse(
        id=mat.id, name=mat.name, sku=mat.sku, category=mat.category,
        unit=mat.unit, unit_cost=mat.unit_cost, stock_qty=mat.stock_qty,
        min_stock_qty=mat.min_stock_qty, description=mat.description,
        created_at=mat.created_at
    )

@router.put("/materials/{material_id}", response_model=MaterialResponse)
def update_material(
    material_id: str,
    data: MaterialCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user has appropriate role in any organization
    user_orgs = get_user_org_ids(user)
    has_permission = False
    for org_id in user_orgs:
        role = get_user_role_in_org(user.id, org_id, db)
        if role in ["org_admin", "pm", "field_lead"]:
            has_permission = True
            break
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to update materials")
    
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    for field in ['name', 'sku', 'category', 'unit', 'unit_cost', 'stock_qty', 'min_stock_qty', 'description']:
        setattr(mat, field, getattr(data, field))
    db.commit()
    db.refresh(mat)
    return MaterialResponse(
        id=mat.id, name=mat.name, sku=mat.sku, category=mat.category,
        unit=mat.unit, unit_cost=mat.unit_cost, stock_qty=mat.stock_qty,
        min_stock_qty=mat.min_stock_qty, description=mat.description,
        created_at=mat.created_at
    )

@router.delete("/materials/{material_id}", status_code=204)
def delete_material(
    material_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user has appropriate role in any organization
    user_orgs = get_user_org_ids(user)
    has_permission = False
    for org_id in user_orgs:
        role = get_user_role_in_org(user.id, org_id, db)
        if role in ["org_admin", "pm", "field_lead"]:
            has_permission = True
            break
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to delete materials")
    
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    db.delete(mat)
    db.commit()

@router.get("/tasks/{task_id}/materials", response_model=list[TaskMaterialResponse])
def list_task_materials(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = db.query(Project).filter(Project.id == task.project_id).first()
    require_project_access(user, project)
    
    tms = db.query(TaskMaterial).filter(TaskMaterial.task_id == task_id).all()
    result = []
    for tm in tms:
        mat = db.query(Material).filter(Material.id == tm.material_id).first()
        result.append(TaskMaterialResponse(
            id=tm.id, task_id=tm.task_id, material_id=tm.material_id,
            material_name=mat.name if mat else None,
            material_sku=mat.sku if mat else None,
            planned_qty=tm.planned_qty, actual_qty=tm.actual_qty,
            created_at=tm.created_at
        ))
    return result

@router.post("/tasks/{task_id}/materials", response_model=TaskMaterialResponse, status_code=201)
def add_task_material(
    task_id: str,
    data: TaskMaterialCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = db.query(Project).filter(Project.id == task.project_id).first()
    require_project_access(user, project)
    
    mat = db.query(Material).filter(Material.id == data.material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    
    tm = TaskMaterial(
        task_id=task_id, material_id=data.material_id,
        planned_qty=data.planned_qty
    )
    db.add(tm)
    db.commit()
    db.refresh(tm)
    return TaskMaterialResponse(
        id=tm.id, task_id=tm.task_id, material_id=tm.material_id,
        material_name=mat.name, material_sku=mat.sku,
        planned_qty=tm.planned_qty, actual_qty=tm.actual_qty,
        created_at=tm.created_at
    )

@router.put("/tasks/{task_id}/materials/{tm_id}", response_model=TaskMaterialResponse)
def update_task_material(
    task_id: str,
    tm_id: str,
    data: TaskMaterialCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = db.query(Project).filter(Project.id == task.project_id).first()
    require_project_access(user, project)
    
    tm = db.query(TaskMaterial).filter(TaskMaterial.id == tm_id, TaskMaterial.task_id == task_id).first()
    if not tm:
        raise HTTPException(status_code=404, detail="Task material not found")
    
    tm.planned_qty = data.planned_qty
    tm.actual_qty = getattr(data, 'actual_qty', tm.actual_qty)
    db.commit()
    db.refresh(tm)
    mat = db.query(Material).filter(Material.id == tm.material_id).first()
    return TaskMaterialResponse(
        id=tm.id, task_id=tm.task_id, material_id=tm.material_id,
        material_name=mat.name if mat else None,
        material_sku=mat.sku if mat else None,
        planned_qty=tm.planned_qty, actual_qty=tm.actual_qty,
        created_at=tm.created_at
    )

@router.get("/materials/low-stock", response_model=list[MaterialResponse])
def low_stock_alerts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mats = db.query(Material).filter(Material.stock_qty <= Material.min_stock_qty, Material.min_stock_qty > 0).all()
    return [MaterialResponse(
        id=m.id, name=m.name, sku=m.sku, category=m.category,
        unit=m.unit, unit_cost=m.unit_cost, stock_qty=m.stock_qty,
        min_stock_qty=m.min_stock_qty, description=m.description,
        created_at=m.created_at
    ) for m in mats]
