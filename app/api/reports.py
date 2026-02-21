import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, case
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import Task, TaskStatus, Project, User, FieldEntry, TaskType, WorkPackage

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_project_ids(user: User, db: Session, project_id: str = None):
    org_ids = [m.org_id for m in user.memberships]
    q = db.query(Project).filter(
        (Project.executing_org_id.in_(org_ids)) | (Project.owner_org_id.in_(org_ids))
    )
    if project_id:
        q = q.filter(Project.id == project_id)
    projects = q.all()
    return [p.id for p in projects]


@router.get("/progress")
def get_progress(
    project_id: str = Query(None),
    group_by: str = Query("status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project_ids = _get_project_ids(user, db, project_id)
    if not project_ids:
        return []

    if group_by == "task_type":
        rows = db.query(
            TaskType.name.label("group_name"),
            func.coalesce(func.sum(Task.planned_qty), 0).label("planned_qty"),
            func.coalesce(func.sum(Task.actual_qty), 0).label("actual_qty"),
            func.count(Task.id).label("task_count"),
            func.sum(case(
                (Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED]), 1),
                else_=0
            )).label("completed_count")
        ).join(TaskType, Task.task_type_id == TaskType.id, isouter=True).filter(
            Task.project_id.in_(project_ids)
        ).group_by(TaskType.name).all()
    elif group_by == "work_package":
        rows = db.query(
            func.coalesce(WorkPackage.name, "Unassigned").label("group_name"),
            func.coalesce(func.sum(Task.planned_qty), 0).label("planned_qty"),
            func.coalesce(func.sum(Task.actual_qty), 0).label("actual_qty"),
            func.count(Task.id).label("task_count"),
            func.sum(case(
                (Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED]), 1),
                else_=0
            )).label("completed_count")
        ).join(WorkPackage, Task.work_package_id == WorkPackage.id, isouter=True).filter(
            Task.project_id.in_(project_ids)
        ).group_by(WorkPackage.name).all()
    else:
        rows = db.query(
            Task.status.label("group_name"),
            func.coalesce(func.sum(Task.planned_qty), 0).label("planned_qty"),
            func.coalesce(func.sum(Task.actual_qty), 0).label("actual_qty"),
            func.count(Task.id).label("task_count"),
            func.sum(case(
                (Task.status.in_([TaskStatus.APPROVED, TaskStatus.BILLED]), 1),
                else_=0
            )).label("completed_count")
        ).filter(
            Task.project_id.in_(project_ids)
        ).group_by(Task.status).all()

    result = []
    for row in rows:
        group_name = row.group_name
        if group_name is None:
            group_name = "Unknown"
        if hasattr(group_name, 'value'):
            group_name = group_name.value
        result.append({
            "group": str(group_name),
            "planned_qty": float(row.planned_qty),
            "actual_qty": float(row.actual_qty),
            "task_count": int(row.task_count),
            "completed_count": int(row.completed_count)
        })

    return result


@router.get("/productivity")
def get_productivity(
    project_id: str = Query(None),
    days: int = Query(30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project_ids = _get_project_ids(user, db, project_id)
    if not project_ids:
        return []

    since = datetime.utcnow() - timedelta(days=days)

    rows = db.query(
        cast(FieldEntry.created_at, Date).label("date"),
        func.coalesce(func.sum(FieldEntry.qty_delta), 0).label("qty_completed"),
        func.coalesce(func.sum(FieldEntry.labor_hours), 0).label("labor_hours"),
        func.count(FieldEntry.id).label("entries_count")
    ).join(Task, FieldEntry.task_id == Task.id).filter(
        Task.project_id.in_(project_ids),
        FieldEntry.created_at >= since
    ).group_by(cast(FieldEntry.created_at, Date)).order_by(cast(FieldEntry.created_at, Date)).all()

    return [{
        "date": row.date.isoformat() if row.date else None,
        "qty_completed": float(row.qty_completed),
        "labor_hours": float(row.labor_hours),
        "entries_count": int(row.entries_count)
    } for row in rows]


@router.get("/crew-performance")
def get_crew_performance(
    project_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project_ids = _get_project_ids(user, db, project_id)
    if not project_ids:
        return []

    rows = db.query(
        FieldEntry.user_id,
        User.full_name.label("user_name"),
        func.coalesce(func.sum(FieldEntry.qty_delta), 0).label("total_qty"),
        func.coalesce(func.sum(FieldEntry.labor_hours), 0).label("total_hours"),
        func.count(FieldEntry.id).label("entries_count")
    ).join(Task, FieldEntry.task_id == Task.id).join(
        User, FieldEntry.user_id == User.id
    ).filter(
        Task.project_id.in_(project_ids)
    ).group_by(FieldEntry.user_id, User.full_name).all()

    return [{
        "user_id": row.user_id,
        "user_name": row.user_name,
        "total_qty": float(row.total_qty),
        "total_hours": float(row.total_hours),
        "entries_count": int(row.entries_count),
        "avg_qty_per_hour": round(float(row.total_qty) / float(row.total_hours), 2) if row.total_hours and float(row.total_hours) > 0 else 0
    } for row in rows]


@router.get("/export-csv")
def export_csv(
    project_id: str = Query(None),
    report_type: str = Query("progress"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "progress":
        data = get_progress(project_id=project_id, group_by="status", user=user, db=db)
        writer.writerow(["Group", "Planned Qty", "Actual Qty", "Task Count", "Completed Count"])
        for row in data:
            writer.writerow([row["group"], row["planned_qty"], row["actual_qty"], row["task_count"], row["completed_count"]])
    elif report_type == "productivity":
        data = get_productivity(project_id=project_id, days=30, user=user, db=db)
        writer.writerow(["Date", "Qty Completed", "Labor Hours", "Entries Count"])
        for row in data:
            writer.writerow([row["date"], row["qty_completed"], row["labor_hours"], row["entries_count"]])
    elif report_type == "crew":
        data = get_crew_performance(project_id=project_id, user=user, db=db)
        writer.writerow(["User ID", "User Name", "Total Qty", "Total Hours", "Entries Count", "Avg Qty/Hour"])
        for row in data:
            writer.writerow([row["user_id"], row["user_name"], row["total_qty"], row["total_hours"], row["entries_count"], row["avg_qty_per_hour"]])
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")

    output.seek(0)
    filename = f"report_{report_type}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
