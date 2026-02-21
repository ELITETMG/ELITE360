import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import (
    Task, Project, User, TaskStatus, ProjectBudget,
    FieldEntry, Activity, Material
)
from app.services import ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_project_kpis(db: Session, project_id: str) -> dict:
    total = db.query(func.count(Task.id)).filter(Task.project_id == project_id).scalar() or 0
    completed = db.query(func.count(Task.id)).filter(
        Task.project_id == project_id,
        Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED])
    ).scalar() or 0
    in_progress = db.query(func.count(Task.id)).filter(
        Task.project_id == project_id, Task.status == TaskStatus.IN_PROGRESS
    ).scalar() or 0
    rework = db.query(func.count(Task.id)).filter(
        Task.project_id == project_id,
        Task.status.in_([TaskStatus.REWORK, TaskStatus.FAILED_INSPECTION])
    ).scalar() or 0
    planned_qty = float(db.query(func.coalesce(func.sum(Task.planned_qty), 0)).filter(Task.project_id == project_id).scalar() or 0)
    actual_qty = float(db.query(func.coalesce(func.sum(Task.actual_qty), 0)).filter(Task.project_id == project_id).scalar() or 0)
    planned_cost = float(db.query(func.coalesce(func.sum(Task.total_cost), 0)).filter(Task.project_id == project_id).scalar() or 0)
    actual_cost = float(db.query(func.coalesce(func.sum(Task.actual_cost), 0)).filter(Task.project_id == project_id).scalar() or 0)
    budget = db.query(ProjectBudget).filter(ProjectBudget.project_id == project_id).first()

    completion_pct = (completed / total * 100) if total > 0 else 0
    spi = (completed / (total * 0.7)) if total > 0 else 0
    cpi = (planned_cost / actual_cost) if actual_cost > 0 else 0
    health = 'good'
    if rework > total * 0.15 or (cpi > 0 and cpi < 0.8):
        health = 'critical'
    elif rework > total * 0.05 or (cpi > 0 and cpi < 0.95):
        health = 'at_risk'

    return {
        "completion_pct": round(completion_pct, 1), "total_tasks": total,
        "completed_tasks": completed, "in_progress_tasks": in_progress,
        "rework_tasks": rework, "spi": round(spi, 2), "cpi": round(cpi, 2),
        "health_status": health, "budget_total": budget.total_budget if budget else 0,
        "budget_spent": actual_cost, "planned_qty": planned_qty, "actual_qty": actual_qty,
    }


def _get_conflicts_summary(db: Session, project_id: str) -> dict:
    try:
        crossing_count = db.execute(text("""
            SELECT COUNT(*) FROM tasks a JOIN tasks b ON a.id < b.id AND a.project_id = b.project_id
            WHERE a.project_id = :pid AND a.geometry IS NOT NULL AND b.geometry IS NOT NULL
            AND ST_Intersects(a.geometry, b.geometry)
            AND GeometryType(a.geometry) IN ('LINESTRING','MULTILINESTRING')
            AND GeometryType(b.geometry) IN ('LINESTRING','MULTILINESTRING')
        """), {"pid": project_id}).scalar() or 0
        return {"total_conflicts": crossing_count, "crossings": crossing_count}
    except:
        return {"total_conflicts": 0, "crossings": 0}


def _get_route_stats(db: Session, project_id: str) -> dict:
    try:
        result = db.execute(text("""
            SELECT COUNT(*) as total,
                COALESCE(SUM(CASE WHEN GeometryType(geometry) IN ('LINESTRING','MULTILINESTRING')
                    THEN ST_Length(geometry::geography) ELSE 0 END), 0) as length_m
            FROM tasks WHERE project_id = :pid AND geometry IS NOT NULL
        """), {"pid": project_id}).fetchone()
        length_m = float(result.length_m)
        return {
            "total_tasks_with_geometry": result.total,
            "total_fiber_length_meters": round(length_m, 2),
            "total_fiber_length_feet": round(length_m * 3.28084, 2),
            "total_fiber_length_miles": round(length_m * 0.000621371, 3),
        }
    except:
        return {"total_tasks_with_geometry": 0, "total_fiber_length_meters": 0, "total_fiber_length_feet": 0, "total_fiber_length_miles": 0}


@router.get("/projects/{project_id}/insights")
def get_project_insights(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)

    kpis = _get_project_kpis(db, project_id)
    conflicts = _get_conflicts_summary(db, project_id)
    route_stats = _get_route_stats(db, project_id)
    budget = db.query(ProjectBudget).filter(ProjectBudget.project_id == project_id).first()
    budget_data = {
        "total_budget": budget.total_budget if budget else 0,
        "spent": kpis["budget_spent"],
        "remaining": (budget.total_budget - kpis["budget_spent"]) if budget else 0,
    }

    insights = ai_service.generate_project_insights(kpis, conflicts, route_stats, budget_data)
    return {"project_id": project_id, "insights": insights}


@router.get("/projects/{project_id}/recommendations")
def get_task_recommendations(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)

    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    kpis = _get_project_kpis(db, project_id)

    task_data = []
    for t in tasks:
        tt_name = t.task_type.name if t.task_type else ""
        task_data.append({
            "name": t.name, "status": t.status.value if t.status else "",
            "priority": t.priority or "medium", "task_type_name": tt_name,
            "planned_qty": float(t.planned_qty or 0), "actual_qty": float(t.actual_qty or 0),
            "total_cost": float(t.total_cost or 0),
        })

    recs = ai_service.generate_task_recommendations(task_data, kpis)
    return {"project_id": project_id, "recommendations": recs}


@router.get("/projects/{project_id}/briefing")
def get_daily_briefing(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)

    kpis = _get_project_kpis(db, project_id)

    activities = db.query(Activity).filter(Activity.project_id == project_id).order_by(Activity.created_at.desc()).limit(15).all()
    activity_data = [{"action": a.action, "entity_name": a.entity_name, "user_name": ""} for a in activities]

    low_stock = db.query(Material).filter(Material.stock_qty <= Material.min_stock_qty, Material.min_stock_qty > 0).all()
    low_stock_data = [{"name": m.name} for m in low_stock]

    briefing = ai_service.generate_daily_briefing(kpis, activity_data, low_stock_data)
    return {"project_id": project_id, "briefing": briefing}


@router.get("/reports/summary")
def get_report_summary(
    report_type: str = Query("progress", description="progress, productivity, or crew"),
    project_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            require_project_access(user, project)

    report_data = {}
    if report_type == "progress" and project_id:
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        status_counts = {}
        for t in tasks:
            s = t.status.value if t.status else "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1
        report_data = {"task_count": len(tasks), "by_status": status_counts}
    elif report_type == "productivity" and project_id:
        entries = db.query(FieldEntry).join(Task).filter(Task.project_id == project_id).order_by(FieldEntry.created_at.desc()).limit(50).all()
        report_data = {"entry_count": len(entries), "total_qty": sum(float(e.qty_installed or 0) for e in entries)}
    elif report_type == "crew" and project_id:
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        report_data = {"task_count": len(tasks), "completed": sum(1 for t in tasks if t.status in [TaskStatus.APPROVED, TaskStatus.BILLED])}

    summary = ai_service.generate_report_summary(report_data, report_type)
    return {"report_type": report_type, "summary": summary}


@router.get("/tasks/{task_id}/anomalies")
def detect_task_anomalies(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if project:
        require_project_access(user, project)

    entries = db.query(FieldEntry).filter(FieldEntry.task_id == task_id).order_by(FieldEntry.created_at.desc()).all()
    entry_data = [{"qty_installed": float(e.qty_installed or 0), "created_at": str(e.created_at), "user_name": ""} for e in entries]
    task_info = {"name": task.name, "planned_qty": float(task.planned_qty or 0), "actual_qty": float(task.actual_qty or 0)}

    anomalies = ai_service.detect_field_anomalies(entry_data, task_info)
    return {"task_id": task_id, "anomalies": anomalies}
