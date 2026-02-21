import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import Task, Project, User

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/projects/{project_id}/conflicts")
def detect_conflicts(
    project_id: str,
    buffer_meters: float = Query(5.0, description="Buffer distance in meters for proximity detection"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    conflicts = []
    
    crossing_sql = text("""
        SELECT a.id as task_a_id, a.name as task_a_name,
               b.id as task_b_id, b.name as task_b_name,
               ST_AsGeoJSON(ST_Intersection(a.geometry, b.geometry)) as intersection_geojson,
               'crossing' as conflict_type
        FROM tasks a
        JOIN tasks b ON a.id < b.id AND a.project_id = b.project_id
        WHERE a.project_id = :pid
          AND a.geometry IS NOT NULL AND b.geometry IS NOT NULL
          AND ST_Intersects(a.geometry, b.geometry)
          AND GeometryType(a.geometry) IN ('LINESTRING', 'MULTILINESTRING')
          AND GeometryType(b.geometry) IN ('LINESTRING', 'MULTILINESTRING')
        LIMIT 100
    """)
    
    crossing_results = db.execute(crossing_sql, {"pid": project_id}).fetchall()
    for row in crossing_results:
        conflicts.append({
            "type": "crossing",
            "severity": "warning",
            "task_a": {"id": row.task_a_id, "name": row.task_a_name},
            "task_b": {"id": row.task_b_id, "name": row.task_b_name},
            "intersection": json.loads(row.intersection_geojson) if row.intersection_geojson else None,
            "message": f"Spans '{row.task_a_name}' and '{row.task_b_name}' cross each other"
        })
    
    proximity_sql = text("""
        SELECT a.id as task_a_id, a.name as task_a_name,
               b.id as task_b_id, b.name as task_b_name,
               ST_Distance(
                   ST_Transform(a.geometry, 3857),
                   ST_Transform(b.geometry, 3857)
               ) as distance_meters,
               'proximity' as conflict_type
        FROM tasks a
        JOIN tasks b ON a.id < b.id AND a.project_id = b.project_id
        WHERE a.project_id = :pid
          AND a.geometry IS NOT NULL AND b.geometry IS NOT NULL
          AND NOT ST_Intersects(a.geometry, b.geometry)
          AND ST_DWithin(
              ST_Transform(a.geometry, 3857),
              ST_Transform(b.geometry, 3857),
              :buffer
          )
          AND GeometryType(a.geometry) IN ('LINESTRING', 'MULTILINESTRING')
          AND GeometryType(b.geometry) IN ('LINESTRING', 'MULTILINESTRING')
        LIMIT 50
    """)
    
    proximity_results = db.execute(proximity_sql, {"pid": project_id, "buffer": buffer_meters}).fetchall()
    for row in proximity_results:
        conflicts.append({
            "type": "proximity",
            "severity": "info",
            "task_a": {"id": row.task_a_id, "name": row.task_a_name},
            "task_b": {"id": row.task_b_id, "name": row.task_b_name},
            "distance_meters": round(row.distance_meters, 2),
            "message": f"Spans '{row.task_a_name}' and '{row.task_b_name}' are within {round(row.distance_meters, 1)}m"
        })
    
    overlap_sql = text("""
        SELECT a.id as task_a_id, a.name as task_a_name,
               b.id as task_b_id, b.name as task_b_name,
               ST_Area(ST_Intersection(a.geometry, b.geometry)::geography) as overlap_area_sqm,
               'overlap' as conflict_type
        FROM tasks a
        JOIN tasks b ON a.id < b.id AND a.project_id = b.project_id
        WHERE a.project_id = :pid
          AND a.geometry IS NOT NULL AND b.geometry IS NOT NULL
          AND ST_Intersects(a.geometry, b.geometry)
          AND GeometryType(a.geometry) = 'POLYGON'
          AND GeometryType(b.geometry) = 'POLYGON'
        LIMIT 50
    """)
    
    overlap_results = db.execute(overlap_sql, {"pid": project_id}).fetchall()
    for row in overlap_results:
        conflicts.append({
            "type": "overlap",
            "severity": "warning",
            "task_a": {"id": row.task_a_id, "name": row.task_a_name},
            "task_b": {"id": row.task_b_id, "name": row.task_b_name},
            "overlap_area_sqm": round(float(row.overlap_area_sqm), 2),
            "message": f"Zones '{row.task_a_name}' and '{row.task_b_name}' overlap ({round(float(row.overlap_area_sqm), 1)} sq m)"
        })
    
    return {
        "project_id": project_id,
        "total_conflicts": len(conflicts),
        "crossings": len([c for c in conflicts if c["type"] == "crossing"]),
        "proximities": len([c for c in conflicts if c["type"] == "proximity"]),
        "overlaps": len([c for c in conflicts if c["type"] == "overlap"]),
        "conflicts": conflicts
    }


@router.get("/projects/{project_id}/route-stats")
def route_statistics(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    stats_sql = text("""
        SELECT 
            COUNT(*) as total_tasks,
            COUNT(CASE WHEN GeometryType(geometry) IN ('LINESTRING', 'MULTILINESTRING') THEN 1 END) as line_tasks,
            COUNT(CASE WHEN GeometryType(geometry) = 'POINT' THEN 1 END) as point_tasks,
            COUNT(CASE WHEN GeometryType(geometry) = 'POLYGON' THEN 1 END) as polygon_tasks,
            COALESCE(SUM(CASE WHEN GeometryType(geometry) IN ('LINESTRING', 'MULTILINESTRING') 
                THEN ST_Length(geometry::geography) ELSE 0 END), 0) as total_length_meters,
            COALESCE(SUM(CASE WHEN GeometryType(geometry) = 'POLYGON'
                THEN ST_Area(geometry::geography) ELSE 0 END), 0) as total_area_sqm,
            ST_AsGeoJSON(ST_Envelope(ST_Collect(geometry))) as bbox_geojson
        FROM tasks
        WHERE project_id = :pid AND geometry IS NOT NULL
    """)
    
    result = db.execute(stats_sql, {"pid": project_id}).fetchone()
    
    return {
        "project_id": project_id,
        "total_tasks": result.total_tasks,
        "geometry_breakdown": {
            "lines": result.line_tasks,
            "points": result.point_tasks,
            "polygons": result.polygon_tasks
        },
        "total_fiber_length_meters": round(float(result.total_length_meters), 2),
        "total_fiber_length_feet": round(float(result.total_length_meters) * 3.28084, 2),
        "total_fiber_length_miles": round(float(result.total_length_meters) * 0.000621371, 3),
        "total_zone_area_sqm": round(float(result.total_area_sqm), 2),
        "total_zone_area_acres": round(float(result.total_area_sqm) * 0.000247105, 3),
        "bounding_box": json.loads(result.bbox_geojson) if result.bbox_geojson else None
    }


@router.get("/projects/{project_id}/kpis")
def project_kpis(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    from app.models.models import TaskStatus, ProjectBudget, FieldEntry
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    total = db.query(func.count(Task.id)).filter(Task.project_id == project_id).scalar() or 0
    completed = db.query(func.count(Task.id)).filter(
        Task.project_id == project_id,
        Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED])
    ).scalar() or 0
    in_progress = db.query(func.count(Task.id)).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.IN_PROGRESS
    ).scalar() or 0
    rework = db.query(func.count(Task.id)).filter(
        Task.project_id == project_id,
        Task.status.in_([TaskStatus.REWORK, TaskStatus.FAILED_INSPECTION])
    ).scalar() or 0
    
    planned_qty = db.query(func.coalesce(func.sum(Task.planned_qty), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    actual_qty = db.query(func.coalesce(func.sum(Task.actual_qty), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    
    planned_cost = db.query(func.coalesce(func.sum(Task.total_cost), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    actual_cost = db.query(func.coalesce(func.sum(Task.actual_cost), 0)).filter(
        Task.project_id == project_id
    ).scalar() or 0
    
    budget = db.query(ProjectBudget).filter(ProjectBudget.project_id == project_id).first()
    
    completion_pct = (completed / total * 100) if total > 0 else 0
    qty_progress = (float(actual_qty) / float(planned_qty) * 100) if planned_qty > 0 else 0
    
    spi = (completed / (total * 0.7)) if total > 0 else 0
    cpi = (float(planned_cost) / float(actual_cost)) if actual_cost > 0 else 0
    
    health = 'good'
    if rework > total * 0.15 or (cpi > 0 and cpi < 0.8):
        health = 'critical'
    elif rework > total * 0.05 or (cpi > 0 and cpi < 0.95):
        health = 'at_risk'
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_entries = db.query(func.count(FieldEntry.id)).filter(
        FieldEntry.task_id.in_(db.query(Task.id).filter(Task.project_id == project_id)),
        FieldEntry.created_at >= week_ago
    ).scalar() or 0
    
    return {
        "project_id": project_id,
        "completion_pct": round(completion_pct, 1),
        "qty_progress_pct": round(qty_progress, 1),
        "total_tasks": total,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "rework_tasks": rework,
        "spi": round(spi, 2),
        "cpi": round(cpi, 2),
        "health_status": health,
        "budget_total": budget.total_budget if budget else 0,
        "budget_spent": float(actual_cost),
        "budget_remaining": (budget.total_budget - float(actual_cost)) if budget else 0,
        "weekly_field_entries": weekly_entries,
        "planned_qty": float(planned_qty),
        "actual_qty": float(actual_qty)
    }
