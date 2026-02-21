from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import uuid, json, asyncio
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (User, Crew, CrewMember, DispatchJob, DispatchJobStatus,
    Project, Task, OrgMember)

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


class DispatchConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = DispatchConnectionManager()


def serialize_job(job, db: Session) -> dict:
    crew_info = None
    if job.crew:
        crew_info = {
            "id": job.crew.id,
            "name": job.crew.name,
            "color": job.crew.color
        }

    project_info = None
    if job.project:
        project_info = {
            "id": job.project.id,
            "name": job.project.name
        }

    task_info = None
    if job.task:
        task_info = {
            "id": job.task.id,
            "name": job.task.name
        }

    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "status": job.status.value if job.status else None,
        "priority": job.priority,
        "job_type": job.job_type,
        "scheduled_start": job.scheduled_start.isoformat() if job.scheduled_start else None,
        "scheduled_end": job.scheduled_end.isoformat() if job.scheduled_end else None,
        "actual_start": job.actual_start.isoformat() if job.actual_start else None,
        "actual_end": job.actual_end.isoformat() if job.actual_end else None,
        "estimated_duration_hrs": job.estimated_duration_hrs,
        "crew": crew_info,
        "crew_id": job.crew_id,
        "project": project_info,
        "project_id": job.project_id,
        "task": task_info,
        "task_id": job.task_id,
        "location_address": job.location_address,
        "location_lat": job.location_lat,
        "location_lng": job.location_lng,
        "notes": job.notes,
        "color": job.color,
        "created_by": job.created_by,
        "assigned_at": job.assigned_at.isoformat() if job.assigned_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _get_user_org(user: User, db: Session):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="User has no organization")
    return membership.org_id


@router.get("/crews")
def list_crews(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_id = _get_user_org(current_user, db)
    crews = db.query(Crew).options(
        joinedload(Crew.members).joinedload(CrewMember.user)
    ).filter(Crew.is_active == True, Crew.org_id == org_id).all()

    result = []
    for crew in crews:
        members = []
        for m in crew.members:
            members.append({
                "user_id": m.user_id,
                "full_name": m.user.full_name if m.user else None,
                "role_in_crew": m.role_in_crew
            })
        result.append({
            "id": crew.id,
            "name": crew.name,
            "color": crew.color,
            "vehicle": crew.vehicle,
            "skills": crew.skills,
            "is_active": crew.is_active,
            "member_count": len(members),
            "members": members,
            "description": crew.description,
            "max_jobs_per_day": crew.max_jobs_per_day,
        })
    return result


@router.post("/crews")
def create_crew(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_ids = [m.org_id for m in current_user.memberships]
    if not org_ids:
        raise HTTPException(status_code=400, detail="User has no organization")

    crew = Crew(
        id=str(uuid.uuid4()),
        org_id=org_ids[0],
        name=data.get("name", "New Crew"),
        description=data.get("description"),
        color=data.get("color", "#3B82F6"),
        vehicle=data.get("vehicle"),
        skills=data.get("skills"),
        max_jobs_per_day=data.get("max_jobs_per_day", 5),
    )
    db.add(crew)
    db.commit()
    db.refresh(crew)
    return {
        "id": crew.id,
        "name": crew.name,
        "color": crew.color,
        "vehicle": crew.vehicle,
        "skills": crew.skills,
        "is_active": crew.is_active,
        "description": crew.description,
        "max_jobs_per_day": crew.max_jobs_per_day,
    }


@router.put("/crews/{crew_id}")
def update_crew(crew_id: str, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    crew = db.query(Crew).filter(Crew.id == crew_id).first()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    for field in ["name", "description", "color", "vehicle", "skills", "max_jobs_per_day", "is_active"]:
        if field in data:
            setattr(crew, field, data[field])

    db.commit()
    db.refresh(crew)
    return {
        "id": crew.id,
        "name": crew.name,
        "color": crew.color,
        "vehicle": crew.vehicle,
        "skills": crew.skills,
        "is_active": crew.is_active,
        "description": crew.description,
        "max_jobs_per_day": crew.max_jobs_per_day,
    }


@router.delete("/crews/{crew_id}")
def deactivate_crew(crew_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    crew = db.query(Crew).filter(Crew.id == crew_id).first()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    crew.is_active = False
    db.commit()
    return {"message": "Crew deactivated"}


@router.post("/crews/{crew_id}/members")
def add_crew_member(crew_id: str, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    crew = db.query(Crew).filter(Crew.id == crew_id).first()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    existing = db.query(CrewMember).filter(
        CrewMember.crew_id == crew_id,
        CrewMember.user_id == user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already in crew")

    member = CrewMember(
        id=str(uuid.uuid4()),
        crew_id=crew_id,
        user_id=user_id,
        role_in_crew=data.get("role_in_crew", "member"),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "crew_id": member.crew_id, "user_id": member.user_id, "role_in_crew": member.role_in_crew}


@router.delete("/crews/{crew_id}/members/{user_id}")
def remove_crew_member(crew_id: str, user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = db.query(CrewMember).filter(
        CrewMember.crew_id == crew_id,
        CrewMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in crew")
    db.delete(member)
    db.commit()
    return {"message": "Member removed from crew"}


@router.get("/jobs")
def list_jobs(
    project_id: str = Query(None),
    crew_id: str = Query(None),
    status: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _get_user_org(current_user, db)
    org_project_ids = [p.id for p in db.query(Project.id).filter(
        (Project.owner_org_id == org_id) | (Project.executing_org_id == org_id)
    ).all()]

    query = db.query(DispatchJob).options(
        joinedload(DispatchJob.crew),
        joinedload(DispatchJob.project),
        joinedload(DispatchJob.task),
    ).filter(DispatchJob.project_id.in_(org_project_ids))

    if project_id:
        query = query.filter(DispatchJob.project_id == project_id)
    if crew_id:
        query = query.filter(DispatchJob.crew_id == crew_id)
    if status:
        query = query.filter(DispatchJob.status == status)
    if date_from:
        query = query.filter(DispatchJob.scheduled_start >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(DispatchJob.scheduled_end <= datetime.fromisoformat(date_to))

    jobs = query.order_by(DispatchJob.scheduled_start.asc().nullslast()).all()
    return [serialize_job(j, db) for j in jobs]


@router.post("/jobs")
async def create_job(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == data.get("project_id")).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job_status = DispatchJobStatus.UNASSIGNED
    assigned_at = None
    if data.get("crew_id"):
        job_status = DispatchJobStatus.SCHEDULED
        assigned_at = datetime.utcnow()

    job = DispatchJob(
        id=str(uuid.uuid4()),
        project_id=data["project_id"],
        task_id=data.get("task_id"),
        crew_id=data.get("crew_id"),
        title=data.get("title", "Untitled Job"),
        description=data.get("description"),
        status=job_status,
        priority=data.get("priority", "medium"),
        job_type=data.get("job_type"),
        scheduled_start=datetime.fromisoformat(data["scheduled_start"]) if data.get("scheduled_start") else None,
        scheduled_end=datetime.fromisoformat(data["scheduled_end"]) if data.get("scheduled_end") else None,
        estimated_duration_hrs=data.get("estimated_duration_hrs"),
        location_address=data.get("location_address"),
        location_lat=data.get("location_lat"),
        location_lng=data.get("location_lng"),
        notes=data.get("notes"),
        color=data.get("color"),
        created_by=current_user.id,
        assigned_at=assigned_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job = db.query(DispatchJob).options(
        joinedload(DispatchJob.crew),
        joinedload(DispatchJob.project),
        joinedload(DispatchJob.task),
    ).filter(DispatchJob.id == job.id).first()

    job_data = serialize_job(job, db)
    await manager.broadcast({"type": "job_created", "job": job_data})
    return job_data


@router.put("/jobs/{job_id}")
async def update_job(job_id: str, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(DispatchJob).filter(DispatchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    old_crew_id = job.crew_id

    for field in ["title", "description", "priority", "job_type", "estimated_duration_hrs",
                   "location_address", "location_lat", "location_lng", "notes", "color",
                   "project_id", "task_id", "crew_id"]:
        if field in data:
            setattr(job, field, data[field])

    if "scheduled_start" in data:
        job.scheduled_start = datetime.fromisoformat(data["scheduled_start"]) if data["scheduled_start"] else None
    if "scheduled_end" in data:
        job.scheduled_end = datetime.fromisoformat(data["scheduled_end"]) if data["scheduled_end"] else None

    if old_crew_id is None and job.crew_id is not None:
        job.assigned_at = datetime.utcnow()
        job.status = DispatchJobStatus.SCHEDULED

    db.commit()
    db.refresh(job)

    job = db.query(DispatchJob).options(
        joinedload(DispatchJob.crew),
        joinedload(DispatchJob.project),
        joinedload(DispatchJob.task),
    ).filter(DispatchJob.id == job.id).first()

    job_data = serialize_job(job, db)
    await manager.broadcast({"type": "job_updated", "job": job_data})
    return job_data


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(DispatchJob).filter(DispatchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    await manager.broadcast({"type": "job_deleted", "job_id": job_id})
    return {"message": "Job deleted"}


@router.put("/jobs/{job_id}/status")
async def update_job_status(job_id: str, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(DispatchJob).filter(DispatchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    new_status = data.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")

    job.status = DispatchJobStatus(new_status)

    if job.status == DispatchJobStatus.COMPLETED:
        job.completed_at = datetime.utcnow()
    if job.status == DispatchJobStatus.IN_PROGRESS:
        job.actual_start = datetime.utcnow()

    db.commit()
    db.refresh(job)

    await manager.broadcast({
        "type": "job_status_changed",
        "job_id": job.id,
        "status": job.status.value,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    })
    return {"id": job.id, "status": job.status.value}


@router.put("/jobs/{job_id}/assign")
async def assign_job(job_id: str, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(DispatchJob).filter(DispatchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    crew_id = data.get("crew_id")
    if not crew_id:
        raise HTTPException(status_code=400, detail="crew_id is required")

    job.crew_id = crew_id
    job.assigned_at = datetime.utcnow()
    if data.get("scheduled_start"):
        job.scheduled_start = datetime.fromisoformat(data["scheduled_start"])
    if data.get("scheduled_end"):
        job.scheduled_end = datetime.fromisoformat(data["scheduled_end"])

    if job.status == DispatchJobStatus.UNASSIGNED:
        job.status = DispatchJobStatus.SCHEDULED

    db.commit()
    db.refresh(job)

    await manager.broadcast({
        "type": "job_assigned",
        "job_id": job.id,
        "crew_id": job.crew_id,
        "scheduled_start": job.scheduled_start.isoformat() if job.scheduled_start else None,
        "scheduled_end": job.scheduled_end.isoformat() if job.scheduled_end else None,
    })
    return serialize_job(job, db)


@router.put("/jobs/{job_id}/reschedule")
async def reschedule_job(job_id: str, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(DispatchJob).filter(DispatchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if data.get("scheduled_start"):
        job.scheduled_start = datetime.fromisoformat(data["scheduled_start"])
    if data.get("scheduled_end"):
        job.scheduled_end = datetime.fromisoformat(data["scheduled_end"])
    if data.get("crew_id"):
        job.crew_id = data["crew_id"]

    db.commit()
    db.refresh(job)

    await manager.broadcast({
        "type": "job_rescheduled",
        "job_id": job.id,
        "crew_id": job.crew_id,
        "scheduled_start": job.scheduled_start.isoformat() if job.scheduled_start else None,
        "scheduled_end": job.scheduled_end.isoformat() if job.scheduled_end else None,
    })
    return serialize_job(job, db)


@router.get("/timeline")
def get_timeline(
    date_from: str = Query(None),
    date_to: str = Query(None),
    project_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_from:
        start_date = datetime.fromisoformat(date_from)
    else:
        today = datetime.utcnow()
        start_date = today - timedelta(days=today.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    if date_to:
        end_date = datetime.fromisoformat(date_to)
    else:
        end_date = start_date + timedelta(days=7)

    org_id = _get_user_org(current_user, db)
    crews = db.query(Crew).options(
        joinedload(Crew.members).joinedload(CrewMember.user)
    ).filter(Crew.is_active == True, Crew.org_id == org_id).all()

    crews_data = []
    for crew in crews:
        members = [{"user_id": m.user_id, "full_name": m.user.full_name if m.user else None, "role_in_crew": m.role_in_crew} for m in crew.members]
        crews_data.append({
            "id": crew.id,
            "name": crew.name,
            "color": crew.color,
            "members": members,
        })

    jobs_query = db.query(DispatchJob).options(
        joinedload(DispatchJob.crew),
        joinedload(DispatchJob.project),
        joinedload(DispatchJob.task),
    ).filter(
        DispatchJob.crew_id.isnot(None),
        DispatchJob.scheduled_start < end_date,
        DispatchJob.scheduled_end > start_date,
    )
    if project_id:
        jobs_query = jobs_query.filter(DispatchJob.project_id == project_id)

    jobs = jobs_query.all()
    jobs_data = [serialize_job(j, db) for j in jobs]

    unassigned_query = db.query(DispatchJob).options(
        joinedload(DispatchJob.project),
        joinedload(DispatchJob.task),
    ).filter(DispatchJob.crew_id.is_(None))
    if project_id:
        unassigned_query = unassigned_query.filter(DispatchJob.project_id == project_id)
    unassigned = unassigned_query.all()
    unassigned_data = [serialize_job(j, db) for j in unassigned]

    return {
        "crews": crews_data,
        "jobs": jobs_data,
        "unassigned": unassigned_data,
    }


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_jobs = db.query(func.count(DispatchJob.id)).scalar()

    by_status = {}
    status_counts = db.query(DispatchJob.status, func.count(DispatchJob.id)).group_by(DispatchJob.status).all()
    for s, c in status_counts:
        by_status[s.value if hasattr(s, 'value') else str(s)] = c

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    jobs_today = db.query(func.count(DispatchJob.id)).filter(
        DispatchJob.scheduled_start >= today,
        DispatchJob.scheduled_start < tomorrow,
    ).scalar()

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    jobs_this_week = db.query(func.count(DispatchJob.id)).filter(
        DispatchJob.scheduled_start >= week_start,
        DispatchJob.scheduled_start < week_end,
    ).scalar()

    crew_utilization = []
    crew_jobs = db.query(
        Crew.id, Crew.name, func.count(DispatchJob.id)
    ).outerjoin(DispatchJob, DispatchJob.crew_id == Crew.id).filter(
        Crew.is_active == True
    ).group_by(Crew.id, Crew.name).all()
    for cid, cname, ccount in crew_jobs:
        crew_utilization.append({"crew_id": cid, "crew_name": cname, "job_count": ccount})

    completed_jobs = db.query(DispatchJob).filter(
        DispatchJob.status == DispatchJobStatus.COMPLETED,
        DispatchJob.completed_at.isnot(None),
        DispatchJob.actual_start.isnot(None),
    ).all()
    avg_completion_time = None
    if completed_jobs:
        total_hours = sum(
            (j.completed_at - j.actual_start).total_seconds() / 3600
            for j in completed_jobs
        )
        avg_completion_time = round(total_hours / len(completed_jobs), 2)

    return {
        "total_jobs": total_jobs,
        "by_status": by_status,
        "jobs_today": jobs_today,
        "jobs_this_week": jobs_this_week,
        "crew_utilization": crew_utilization,
        "avg_completion_time": avg_completion_time,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
