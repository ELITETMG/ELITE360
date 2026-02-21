import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    EmployeeProfile, EmployeeStatus, TimeEntry, PTORequest, PTOStatus, PTOType,
    OnboardingChecklist, OnboardingTask, PerformanceReview, ReviewRating,
    HRTrainingRecord, EmployeeDocument, CompensationRecord, SkillEntry,
    OrgMember, User, BenefitPlan, EmployeeBenefit
)

router = APIRouter(prefix="/api/hr", tags=["hr"])


def _get_user_org(db: Session, user: User):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No org membership")
    return membership.org_id


def _serialize_employee(ep, user_obj=None):
    return {
        "id": ep.id,
        "org_id": ep.org_id,
        "user_id": ep.user_id,
        "full_name": user_obj.full_name if user_obj else (ep.user.full_name if ep.user else None),
        "email": user_obj.email if user_obj else (ep.user.email if ep.user else None),
        "employee_id": ep.employee_id,
        "job_title": ep.job_title,
        "department": ep.department,
        "supervisor_id": ep.supervisor_id,
        "supervisor_name": ep.supervisor.full_name if ep.supervisor else None,
        "status": ep.status.value if ep.status else "active",
        "hire_date": str(ep.hire_date) if ep.hire_date else None,
        "termination_date": str(ep.termination_date) if ep.termination_date else None,
        "employment_type": ep.employment_type,
        "phone": ep.phone,
        "address": ep.address,
        "city": ep.city,
        "state": ep.state,
        "zip_code": ep.zip_code,
        "emergency_contact_name": ep.emergency_contact_name,
        "emergency_contact_phone": ep.emergency_contact_phone,
        "emergency_contact_relation": ep.emergency_contact_relation,
        "date_of_birth": str(ep.date_of_birth) if ep.date_of_birth else None,
        "drivers_license": ep.drivers_license,
        "dl_expiry": str(ep.dl_expiry) if ep.dl_expiry else None,
        "cdl_class": ep.cdl_class,
        "medical_card_expiry": str(ep.medical_card_expiry) if ep.medical_card_expiry else None,
        "shirt_size": ep.shirt_size,
        "boot_size": ep.boot_size,
        "skills_json": ep.skills_json,
        "certifications_json": ep.certifications_json,
        "notes": ep.notes,
        "pto_balance_vacation": float(ep.pto_balance_vacation or 0),
        "pto_balance_sick": float(ep.pto_balance_sick or 0),
        "pto_balance_personal": float(ep.pto_balance_personal or 0),
        "created_at": str(ep.created_at) if ep.created_at else None,
        "updated_at": str(ep.updated_at) if ep.updated_at else None,
    }


@router.get("/employees")
def list_employees(
    status: str = Query(None),
    department: str = Query(None),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(EmployeeProfile, User).join(User, EmployeeProfile.user_id == User.id).filter(
        EmployeeProfile.org_id == org_id
    )
    if status:
        q = q.filter(EmployeeProfile.status == status)
    if department:
        q = q.filter(EmployeeProfile.department == department)
    if search:
        q = q.filter(
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (EmployeeProfile.employee_id.ilike(f"%{search}%"))
        )
    results = q.order_by(User.full_name).all()
    return [_serialize_employee(ep, u) for ep, u in results]


@router.post("/employees")
def create_employee(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    target_user_id = data.get("user_id")
    if target_user_id:
        member_check = db.query(OrgMember).filter(
            OrgMember.org_id == org_id, OrgMember.user_id == target_user_id).first()
        if not member_check:
            raise HTTPException(status_code=400, detail="User is not a member of your organization")
    ep = EmployeeProfile(
        org_id=org_id,
        user_id=target_user_id,
        employee_id=data.get("employee_id"),
        job_title=data.get("job_title"),
        department=data.get("department"),
        supervisor_id=data.get("supervisor_id"),
        status=data.get("status", "active"),
        hire_date=datetime.fromisoformat(data["hire_date"]) if data.get("hire_date") else None,
        employment_type=data.get("employment_type", "full_time"),
        phone=data.get("phone"),
        address=data.get("address"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        emergency_contact_name=data.get("emergency_contact_name"),
        emergency_contact_phone=data.get("emergency_contact_phone"),
        emergency_contact_relation=data.get("emergency_contact_relation"),
        date_of_birth=datetime.fromisoformat(data["date_of_birth"]) if data.get("date_of_birth") else None,
        drivers_license=data.get("drivers_license"),
        dl_expiry=datetime.fromisoformat(data["dl_expiry"]) if data.get("dl_expiry") else None,
        cdl_class=data.get("cdl_class"),
        medical_card_expiry=datetime.fromisoformat(data["medical_card_expiry"]) if data.get("medical_card_expiry") else None,
        shirt_size=data.get("shirt_size"),
        boot_size=data.get("boot_size"),
        skills_json=data.get("skills_json"),
        certifications_json=data.get("certifications_json"),
        notes=data.get("notes"),
        pto_balance_vacation=float(data.get("pto_balance_vacation", 0)),
        pto_balance_sick=float(data.get("pto_balance_sick", 0)),
        pto_balance_personal=float(data.get("pto_balance_personal", 0)),
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return _serialize_employee(ep)


@router.get("/employees/{employee_id}")
def get_employee(employee_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ep = db.query(EmployeeProfile).filter(EmployeeProfile.id == employee_id, EmployeeProfile.org_id == org_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return _serialize_employee(ep)


@router.put("/employees/{employee_id}")
def update_employee(employee_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ep = db.query(EmployeeProfile).filter(EmployeeProfile.id == employee_id, EmployeeProfile.org_id == org_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    fields = ["employee_id", "job_title", "department", "supervisor_id", "employment_type",
              "phone", "address", "city", "state", "zip_code",
              "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
              "drivers_license", "cdl_class", "shirt_size", "boot_size",
              "skills_json", "certifications_json", "notes"]
    for f in fields:
        if f in data:
            setattr(ep, f, data[f])

    if "status" in data:
        ep.status = data["status"]

    float_fields = ["pto_balance_vacation", "pto_balance_sick", "pto_balance_personal"]
    for f in float_fields:
        if f in data:
            setattr(ep, f, float(data[f]) if data[f] is not None else 0)

    date_fields = ["hire_date", "termination_date", "date_of_birth", "dl_expiry", "medical_card_expiry"]
    for f in date_fields:
        if f in data:
            setattr(ep, f, datetime.fromisoformat(data[f]) if data[f] else None)

    db.commit()
    db.refresh(ep)
    return _serialize_employee(ep)


@router.get("/kpis")
def get_employee_kpis(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    total = db.query(func.count(EmployeeProfile.id)).filter(EmployeeProfile.org_id == org_id).scalar() or 0

    by_status = {}
    status_rows = db.query(EmployeeProfile.status, func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id
    ).group_by(EmployeeProfile.status).all()
    for s, c in status_rows:
        by_status[s.value if hasattr(s, 'value') else str(s)] = c

    by_department = {}
    dept_rows = db.query(EmployeeProfile.department, func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id, EmployeeProfile.department.isnot(None)
    ).group_by(EmployeeProfile.department).all()
    for d, c in dept_rows:
        by_department[d] = c

    now = datetime.utcnow()
    active_profiles = db.query(EmployeeProfile).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.status == EmployeeStatus.ACTIVE,
        EmployeeProfile.hire_date.isnot(None)
    ).all()
    if active_profiles:
        total_tenure_days = sum((now - ep.hire_date).days for ep in active_profiles)
        avg_tenure_months = round(total_tenure_days / len(active_profiles) / 30.44, 1)
    else:
        avg_tenure_months = 0

    expiry_window = now + timedelta(days=30)
    dl_expiring = db.query(EmployeeProfile).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.dl_expiry.isnot(None),
        EmployeeProfile.dl_expiry <= expiry_window,
        EmployeeProfile.dl_expiry >= now,
        EmployeeProfile.status == EmployeeStatus.ACTIVE
    ).count()

    med_card_expiring = db.query(EmployeeProfile).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.medical_card_expiry.isnot(None),
        EmployeeProfile.medical_card_expiry <= expiry_window,
        EmployeeProfile.medical_card_expiry >= now,
        EmployeeProfile.status == EmployeeStatus.ACTIVE
    ).count()

    one_year_ago = now - timedelta(days=365)
    terminated_count = db.query(func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.status == EmployeeStatus.TERMINATED,
        EmployeeProfile.termination_date.isnot(None),
        EmployeeProfile.termination_date >= one_year_ago
    ).scalar() or 0
    turnover_rate = round((terminated_count / total * 100), 1) if total > 0 else 0

    total_active = by_status.get("active", 0)
    on_leave = by_status.get("on_leave", 0)
    pending_pto = db.query(func.count(PTORequest.id)).filter(
        PTORequest.org_id == org_id, PTORequest.status == PTOStatus.PENDING).scalar() or 0
    expiring_licenses = dl_expiring + med_card_expiring

    return {
        "total_headcount": total,
        "total_active": total_active,
        "on_leave": on_leave,
        "pending_pto": pending_pto,
        "expiring_licenses": expiring_licenses,
        "departments": by_department,
        "by_status": by_status,
        "by_department": by_department,
        "avg_tenure_months": avg_tenure_months,
        "dl_expiring_30_days": dl_expiring,
        "medical_card_expiring_30_days": med_card_expiring,
        "turnover_rate": turnover_rate,
        "terminated_last_year": terminated_count,
    }


@router.get("/time-entries")
def list_time_entries(
    user_id: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    approved: bool = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(TimeEntry, User).join(User, TimeEntry.user_id == User.id).filter(TimeEntry.org_id == org_id)
    if user_id:
        q = q.filter(TimeEntry.user_id == user_id)
    if start_date:
        q = q.filter(TimeEntry.clock_in >= datetime.fromisoformat(start_date))
    if end_date:
        q = q.filter(TimeEntry.clock_in <= datetime.fromisoformat(end_date))
    if approved is not None:
        q = q.filter(TimeEntry.approved == approved)
    entries = q.order_by(desc(TimeEntry.clock_in)).all()
    return [{
        "id": te.id,
        "org_id": te.org_id,
        "user_id": te.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "project_id": te.project_id,
        "clock_in": str(te.clock_in),
        "clock_out": str(te.clock_out) if te.clock_out else None,
        "break_minutes": te.break_minutes,
        "total_hours": float(te.total_hours) if te.total_hours else None,
        "overtime_hours": float(te.overtime_hours or 0),
        "entry_type": te.entry_type,
        "source": te.source,
        "geo_lat_in": te.geo_lat_in,
        "geo_lng_in": te.geo_lng_in,
        "geo_lat_out": te.geo_lat_out,
        "geo_lng_out": te.geo_lng_out,
        "notes": te.notes,
        "approved": te.approved,
        "approved_by": te.approved_by,
        "created_at": str(te.created_at),
    } for te, u in entries]


@router.post("/time-entries")
def create_time_entry(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    te = TimeEntry(
        org_id=org_id,
        user_id=data.get("user_id", user.id),
        project_id=data.get("project_id"),
        clock_in=datetime.fromisoformat(data["clock_in"]) if data.get("clock_in") else datetime.utcnow(),
        clock_out=datetime.fromisoformat(data["clock_out"]) if data.get("clock_out") else None,
        break_minutes=int(data.get("break_minutes", 0)),
        entry_type=data.get("entry_type", "regular"),
        source=data.get("source", "manual"),
        geo_lat_in=float(data["geo_lat_in"]) if data.get("geo_lat_in") else None,
        geo_lng_in=float(data["geo_lng_in"]) if data.get("geo_lng_in") else None,
        notes=data.get("notes"),
    )
    if te.clock_out and te.clock_in:
        diff = (te.clock_out - te.clock_in).total_seconds() / 3600
        te.total_hours = round(max(diff - (te.break_minutes / 60), 0), 2)
        te.overtime_hours = round(max(te.total_hours - 8, 0), 2)
    db.add(te)
    db.commit()
    db.refresh(te)
    return {"id": te.id, "clock_in": str(te.clock_in), "total_hours": te.total_hours}


@router.put("/time-entries/{entry_id}")
def update_time_entry(entry_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    te = db.query(TimeEntry).filter(TimeEntry.id == entry_id, TimeEntry.org_id == org_id).first()
    if not te:
        raise HTTPException(status_code=404, detail="Time entry not found")

    if "clock_out" in data:
        te.clock_out = datetime.fromisoformat(data["clock_out"]) if data["clock_out"] else None
    if "break_minutes" in data:
        te.break_minutes = int(data["break_minutes"])
    if "notes" in data:
        te.notes = data["notes"]
    if "project_id" in data:
        te.project_id = data["project_id"]
    if "geo_lat_out" in data:
        te.geo_lat_out = float(data["geo_lat_out"]) if data["geo_lat_out"] else None
    if "geo_lng_out" in data:
        te.geo_lng_out = float(data["geo_lng_out"]) if data["geo_lng_out"] else None

    if te.clock_out and te.clock_in:
        diff = (te.clock_out - te.clock_in).total_seconds() / 3600
        te.total_hours = round(max(diff - (te.break_minutes / 60), 0), 2)
        te.overtime_hours = round(max(te.total_hours - 8, 0), 2)

    db.commit()
    db.refresh(te)
    return {"id": te.id, "clock_out": str(te.clock_out) if te.clock_out else None, "total_hours": te.total_hours}


@router.post("/time-entries/{entry_id}/approve")
def approve_time_entry(entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    te = db.query(TimeEntry).filter(TimeEntry.id == entry_id, TimeEntry.org_id == org_id).first()
    if not te:
        raise HTTPException(status_code=404, detail="Time entry not found")
    te.approved = True
    te.approved_by = user.id
    db.commit()
    return {"ok": True, "id": te.id, "approved": True}


@router.get("/time-summary")
def get_time_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    now = datetime.utcnow()

    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    weekly = db.query(
        TimeEntry.user_id,
        User.full_name,
        func.coalesce(func.sum(TimeEntry.total_hours), 0).label("total_hours"),
        func.coalesce(func.sum(TimeEntry.overtime_hours), 0).label("overtime_hours"),
        func.count(TimeEntry.id).label("entry_count")
    ).join(User, TimeEntry.user_id == User.id).filter(
        TimeEntry.org_id == org_id,
        TimeEntry.clock_in >= week_start
    ).group_by(TimeEntry.user_id, User.full_name).all()

    monthly = db.query(
        TimeEntry.user_id,
        User.full_name,
        func.coalesce(func.sum(TimeEntry.total_hours), 0).label("total_hours"),
        func.coalesce(func.sum(TimeEntry.overtime_hours), 0).label("overtime_hours"),
        func.count(TimeEntry.id).label("entry_count")
    ).join(User, TimeEntry.user_id == User.id).filter(
        TimeEntry.org_id == org_id,
        TimeEntry.clock_in >= month_start
    ).group_by(TimeEntry.user_id, User.full_name).all()

    return {
        "week_start": str(week_start),
        "month_start": str(month_start),
        "weekly": [{
            "user_id": r.user_id,
            "full_name": r.full_name,
            "total_hours": round(float(r.total_hours), 2),
            "overtime_hours": round(float(r.overtime_hours), 2),
            "entry_count": r.entry_count,
        } for r in weekly],
        "monthly": [{
            "user_id": r.user_id,
            "full_name": r.full_name,
            "total_hours": round(float(r.total_hours), 2),
            "overtime_hours": round(float(r.overtime_hours), 2),
            "entry_count": r.entry_count,
        } for r in monthly],
    }


@router.get("/pto-requests")
def list_pto_requests(
    status: str = Query(None),
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(PTORequest, User).join(User, PTORequest.user_id == User.id).filter(PTORequest.org_id == org_id)
    if status:
        q = q.filter(PTORequest.status == status)
    if user_id:
        q = q.filter(PTORequest.user_id == user_id)
    results = q.order_by(desc(PTORequest.created_at)).all()
    return [{
        "id": pto.id,
        "org_id": pto.org_id,
        "user_id": pto.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "pto_type": pto.pto_type.value if pto.pto_type else None,
        "start_date": str(pto.start_date),
        "end_date": str(pto.end_date),
        "total_days": float(pto.total_days or 1),
        "status": pto.status.value if pto.status else "pending",
        "reason": pto.reason,
        "approver_id": pto.approver_id,
        "approved_at": str(pto.approved_at) if pto.approved_at else None,
        "denial_reason": pto.denial_reason,
        "notes": pto.notes,
        "created_at": str(pto.created_at),
    } for pto, u in results]


@router.post("/pto-requests")
def create_pto_request(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pto = PTORequest(
        org_id=org_id,
        user_id=data.get("user_id", user.id),
        pto_type=data.get("pto_type", "vacation"),
        start_date=datetime.fromisoformat(data["start_date"]),
        end_date=datetime.fromisoformat(data["end_date"]),
        total_days=float(data.get("total_days", 1)),
        reason=data.get("reason"),
        notes=data.get("notes"),
    )
    db.add(pto)
    db.commit()
    db.refresh(pto)
    return {"id": pto.id, "status": pto.status.value if pto.status else "pending"}


@router.put("/pto-requests/{pto_id}/approve")
def approve_pto_request(pto_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pto = db.query(PTORequest).filter(PTORequest.id == pto_id, PTORequest.org_id == org_id).first()
    if not pto:
        raise HTTPException(status_code=404, detail="PTO request not found")
    pto.status = PTOStatus.APPROVED
    pto.approver_id = user.id
    pto.approved_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": pto.id, "status": "approved"}


@router.put("/pto-requests/{pto_id}/deny")
def deny_pto_request(pto_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    pto = db.query(PTORequest).filter(PTORequest.id == pto_id, PTORequest.org_id == org_id).first()
    if not pto:
        raise HTTPException(status_code=404, detail="PTO request not found")
    pto.status = PTOStatus.DENIED
    pto.approver_id = user.id
    pto.denial_reason = data.get("denial_reason", "")
    db.commit()
    return {"ok": True, "id": pto.id, "status": "denied"}


@router.get("/onboarding-checklists")
def list_onboarding_checklists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    checklists = db.query(OnboardingChecklist).filter(OnboardingChecklist.org_id == org_id).order_by(OnboardingChecklist.name).all()
    return [{
        "id": cl.id,
        "org_id": cl.org_id,
        "name": cl.name,
        "description": cl.description,
        "department": cl.department,
        "is_active": cl.is_active,
        "task_count": len(cl.tasks) if cl.tasks else 0,
        "created_at": str(cl.created_at),
    } for cl in checklists]


@router.post("/onboarding-checklists")
def create_onboarding_checklist(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cl = OnboardingChecklist(
        org_id=org_id,
        name=data["name"],
        description=data.get("description"),
        department=data.get("department"),
        is_active=data.get("is_active", True),
    )
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return {"id": cl.id, "name": cl.name}


@router.get("/onboarding-checklists/{checklist_id}/tasks")
def list_onboarding_tasks(checklist_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cl = db.query(OnboardingChecklist).filter(OnboardingChecklist.id == checklist_id, OnboardingChecklist.org_id == org_id).first()
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")
    tasks = db.query(OnboardingTask).filter(OnboardingTask.checklist_id == checklist_id).order_by(OnboardingTask.sort_order).all()
    return [{
        "id": t.id,
        "checklist_id": t.checklist_id,
        "employee_id": t.employee_id,
        "employee_name": t.employee.full_name if t.employee else None,
        "title": t.title,
        "description": t.description,
        "category": t.category,
        "assigned_to": t.assigned_to,
        "assignee_name": t.assignee.full_name if t.assignee else None,
        "due_days": t.due_days,
        "status": t.status,
        "completed_at": str(t.completed_at) if t.completed_at else None,
        "sort_order": t.sort_order,
        "created_at": str(t.created_at),
    } for t in tasks]


@router.post("/onboarding-tasks")
def create_onboarding_task(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cl = db.query(OnboardingChecklist).filter(OnboardingChecklist.id == data["checklist_id"], OnboardingChecklist.org_id == org_id).first()
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")
    task = OnboardingTask(
        checklist_id=data["checklist_id"],
        employee_id=data.get("employee_id"),
        title=data["title"],
        description=data.get("description"),
        category=data.get("category"),
        assigned_to=data.get("assigned_to"),
        due_days=int(data.get("due_days", 7)),
        sort_order=int(data.get("sort_order", 0)),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title}


@router.put("/onboarding-tasks/{task_id}")
def update_onboarding_task(task_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    task = db.query(OnboardingTask).join(OnboardingChecklist).filter(
        OnboardingTask.id == task_id, OnboardingChecklist.org_id == org_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Onboarding task not found")

    fields = ["title", "description", "category", "assigned_to", "employee_id"]
    for f in fields:
        if f in data:
            setattr(task, f, data[f])
    if "due_days" in data:
        task.due_days = int(data["due_days"])
    if "sort_order" in data:
        task.sort_order = int(data["sort_order"])
    if "status" in data:
        task.status = data["status"]
        if data["status"] == "completed":
            task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return {"ok": True, "id": task.id, "status": task.status}


@router.get("/reviews")
def list_reviews(
    user_id: str = Query(None),
    status: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(PerformanceReview, User).join(User, PerformanceReview.user_id == User.id).filter(
        PerformanceReview.org_id == org_id
    )
    if user_id:
        q = q.filter(PerformanceReview.user_id == user_id)
    if status:
        q = q.filter(PerformanceReview.status == status)
    results = q.order_by(desc(PerformanceReview.review_date)).all()
    return [{
        "id": r.id,
        "org_id": r.org_id,
        "user_id": r.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "reviewer_id": r.reviewer_id,
        "reviewer_name": r.reviewer.full_name if r.reviewer else None,
        "period_start": str(r.period_start) if r.period_start else None,
        "period_end": str(r.period_end) if r.period_end else None,
        "review_date": str(r.review_date) if r.review_date else None,
        "overall_rating": r.overall_rating.value if r.overall_rating else None,
        "technical_score": r.technical_score,
        "safety_score": r.safety_score,
        "teamwork_score": r.teamwork_score,
        "attendance_score": r.attendance_score,
        "quality_score": r.quality_score,
        "strengths": r.strengths,
        "areas_for_improvement": r.areas_for_improvement,
        "goals": r.goals,
        "employee_comments": r.employee_comments,
        "reviewer_comments": r.reviewer_comments,
        "status": r.status,
        "acknowledged_at": str(r.acknowledged_at) if r.acknowledged_at else None,
        "created_at": str(r.created_at),
    } for r, u in results]


@router.post("/reviews")
def create_review(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    review = PerformanceReview(
        org_id=org_id,
        user_id=data["user_id"],
        reviewer_id=data.get("reviewer_id", user.id),
        period_start=datetime.fromisoformat(data["period_start"]) if data.get("period_start") else None,
        period_end=datetime.fromisoformat(data["period_end"]) if data.get("period_end") else None,
        review_date=datetime.fromisoformat(data["review_date"]) if data.get("review_date") else datetime.utcnow(),
        overall_rating=data.get("overall_rating"),
        technical_score=float(data["technical_score"]) if data.get("technical_score") else None,
        safety_score=float(data["safety_score"]) if data.get("safety_score") else None,
        teamwork_score=float(data["teamwork_score"]) if data.get("teamwork_score") else None,
        attendance_score=float(data["attendance_score"]) if data.get("attendance_score") else None,
        quality_score=float(data["quality_score"]) if data.get("quality_score") else None,
        strengths=data.get("strengths"),
        areas_for_improvement=data.get("areas_for_improvement"),
        goals=data.get("goals"),
        reviewer_comments=data.get("reviewer_comments"),
        status=data.get("status", "draft"),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return {"id": review.id, "status": review.status}


@router.get("/reviews/{review_id}")
def get_review(review_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    r = db.query(PerformanceReview).filter(PerformanceReview.id == review_id, PerformanceReview.org_id == org_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    return {
        "id": r.id,
        "org_id": r.org_id,
        "user_id": r.user_id,
        "full_name": r.user.full_name if r.user else None,
        "email": r.user.email if r.user else None,
        "reviewer_id": r.reviewer_id,
        "reviewer_name": r.reviewer.full_name if r.reviewer else None,
        "period_start": str(r.period_start) if r.period_start else None,
        "period_end": str(r.period_end) if r.period_end else None,
        "review_date": str(r.review_date) if r.review_date else None,
        "overall_rating": r.overall_rating.value if r.overall_rating else None,
        "technical_score": r.technical_score,
        "safety_score": r.safety_score,
        "teamwork_score": r.teamwork_score,
        "attendance_score": r.attendance_score,
        "quality_score": r.quality_score,
        "strengths": r.strengths,
        "areas_for_improvement": r.areas_for_improvement,
        "goals": r.goals,
        "employee_comments": r.employee_comments,
        "reviewer_comments": r.reviewer_comments,
        "status": r.status,
        "acknowledged_at": str(r.acknowledged_at) if r.acknowledged_at else None,
        "created_at": str(r.created_at),
        "updated_at": str(r.updated_at) if r.updated_at else None,
    }


@router.put("/reviews/{review_id}")
def update_review(review_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    r = db.query(PerformanceReview).filter(PerformanceReview.id == review_id, PerformanceReview.org_id == org_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")

    fields = ["strengths", "areas_for_improvement", "goals", "employee_comments",
              "reviewer_comments", "status", "overall_rating"]
    for f in fields:
        if f in data:
            setattr(r, f, data[f])

    score_fields = ["technical_score", "safety_score", "teamwork_score", "attendance_score", "quality_score"]
    for f in score_fields:
        if f in data:
            setattr(r, f, float(data[f]) if data[f] is not None else None)

    date_fields = ["period_start", "period_end", "review_date"]
    for f in date_fields:
        if f in data:
            setattr(r, f, datetime.fromisoformat(data[f]) if data[f] else None)

    if data.get("status") == "acknowledged":
        r.acknowledged_at = datetime.utcnow()

    db.commit()
    db.refresh(r)
    return {"ok": True, "id": r.id, "status": r.status}


@router.get("/trainings")
def list_trainings(
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(HRTrainingRecord, User).join(User, HRTrainingRecord.user_id == User.id).filter(
        HRTrainingRecord.org_id == org_id
    )
    if user_id:
        q = q.filter(HRTrainingRecord.user_id == user_id)
    results = q.order_by(desc(HRTrainingRecord.created_at)).all()
    return [{
        "id": tr.id,
        "org_id": tr.org_id,
        "user_id": tr.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "training_name": tr.training_name,
        "training_type": tr.training_type,
        "provider": tr.provider,
        "completion_date": str(tr.completion_date) if tr.completion_date else None,
        "expiry_date": str(tr.expiry_date) if tr.expiry_date else None,
        "certificate_number": tr.certificate_number,
        "status": tr.status,
        "required": tr.required,
        "cost": float(tr.cost or 0),
        "hours": float(tr.hours) if tr.hours else None,
        "notes": tr.notes,
        "created_at": str(tr.created_at),
    } for tr, u in results]


@router.post("/trainings")
def create_training(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    tr = HRTrainingRecord(
        org_id=org_id,
        user_id=data["user_id"],
        training_name=data["training_name"],
        training_type=data.get("training_type"),
        provider=data.get("provider"),
        completion_date=datetime.fromisoformat(data["completion_date"]) if data.get("completion_date") else None,
        expiry_date=datetime.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None,
        certificate_number=data.get("certificate_number"),
        status=data.get("status", "completed"),
        required=data.get("required", False),
        cost=float(data.get("cost", 0)),
        hours=float(data["hours"]) if data.get("hours") else None,
        notes=data.get("notes"),
    )
    db.add(tr)
    db.commit()
    db.refresh(tr)
    return {"id": tr.id, "training_name": tr.training_name}


@router.get("/documents")
def list_employee_documents(
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(EmployeeDocument, User).join(User, EmployeeDocument.user_id == User.id).filter(
        EmployeeDocument.org_id == org_id
    )
    if user_id:
        q = q.filter(EmployeeDocument.user_id == user_id)
    results = q.order_by(desc(EmployeeDocument.created_at)).all()
    return [{
        "id": doc.id,
        "org_id": doc.org_id,
        "user_id": doc.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "title": doc.title,
        "category": doc.category,
        "file_path": doc.file_path,
        "file_type": doc.file_type,
        "expiry_date": str(doc.expiry_date) if doc.expiry_date else None,
        "notes": doc.notes,
        "uploaded_by": doc.uploaded_by,
        "uploader_name": doc.uploader.full_name if doc.uploader else None,
        "created_at": str(doc.created_at),
    } for doc, u in results]


@router.post("/documents")
def create_employee_document(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    doc = EmployeeDocument(
        org_id=org_id,
        user_id=data["user_id"],
        title=data["title"],
        category=data.get("category"),
        file_path=data.get("file_path"),
        file_type=data.get("file_type"),
        expiry_date=datetime.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None,
        notes=data.get("notes"),
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "title": doc.title}


@router.get("/compensation")
def list_compensation(
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(CompensationRecord, User).join(User, CompensationRecord.user_id == User.id).filter(
        CompensationRecord.org_id == org_id
    )
    if user_id:
        q = q.filter(CompensationRecord.user_id == user_id)
    results = q.order_by(desc(CompensationRecord.effective_date)).all()
    return [{
        "id": cr.id,
        "org_id": cr.org_id,
        "user_id": cr.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "pay_type": cr.pay_type,
        "hourly_rate": float(cr.hourly_rate) if cr.hourly_rate else None,
        "salary": float(cr.salary) if cr.salary else None,
        "overtime_rate": float(cr.overtime_rate) if cr.overtime_rate else None,
        "per_diem": float(cr.per_diem) if cr.per_diem else None,
        "effective_date": str(cr.effective_date),
        "end_date": str(cr.end_date) if cr.end_date else None,
        "reason": cr.reason,
        "approved_by": cr.approved_by,
        "approver_name": cr.approver.full_name if cr.approver else None,
        "notes": cr.notes,
        "is_current": cr.is_current,
        "created_at": str(cr.created_at),
    } for cr, u in results]


@router.post("/compensation")
def create_compensation(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cr = CompensationRecord(
        org_id=org_id,
        user_id=data["user_id"],
        pay_type=data.get("pay_type", "hourly"),
        hourly_rate=float(data["hourly_rate"]) if data.get("hourly_rate") else None,
        salary=float(data["salary"]) if data.get("salary") else None,
        overtime_rate=float(data["overtime_rate"]) if data.get("overtime_rate") else None,
        per_diem=float(data["per_diem"]) if data.get("per_diem") else None,
        effective_date=datetime.fromisoformat(data["effective_date"]),
        end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
        reason=data.get("reason"),
        approved_by=data.get("approved_by", user.id),
        notes=data.get("notes"),
        is_current=data.get("is_current", True),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return {"id": cr.id, "effective_date": str(cr.effective_date)}


@router.get("/skills")
def list_skills(
    user_id: str = Query(None),
    skill_name: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(SkillEntry, User).join(User, SkillEntry.user_id == User.id).filter(SkillEntry.org_id == org_id)
    if user_id:
        q = q.filter(SkillEntry.user_id == user_id)
    if skill_name:
        q = q.filter(SkillEntry.skill_name.ilike(f"%{skill_name}%"))
    results = q.order_by(User.full_name, SkillEntry.skill_name).all()
    return [{
        "id": s.id,
        "org_id": s.org_id,
        "user_id": s.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "skill_name": s.skill_name,
        "category": s.category,
        "proficiency_level": s.proficiency_level,
        "years_experience": float(s.years_experience) if s.years_experience else None,
        "last_used": str(s.last_used) if s.last_used else None,
        "certified": s.certified,
        "notes": s.notes,
        "created_at": str(s.created_at),
        "updated_at": str(s.updated_at) if s.updated_at else None,
    } for s, u in results]


@router.post("/skills")
def create_skill(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    skill = SkillEntry(
        org_id=org_id,
        user_id=data["user_id"],
        skill_name=data["skill_name"],
        category=data.get("category"),
        proficiency_level=int(data.get("proficiency_level", 1)),
        years_experience=float(data["years_experience"]) if data.get("years_experience") else None,
        last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
        certified=data.get("certified", False),
        notes=data.get("notes"),
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "skill_name": skill.skill_name}


@router.put("/skills/{skill_id}")
def update_skill(skill_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    skill = db.query(SkillEntry).filter(SkillEntry.id == skill_id, SkillEntry.org_id == org_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill entry not found")

    fields = ["skill_name", "category", "notes"]
    for f in fields:
        if f in data:
            setattr(skill, f, data[f])
    if "proficiency_level" in data:
        skill.proficiency_level = int(data["proficiency_level"])
    if "years_experience" in data:
        skill.years_experience = float(data["years_experience"]) if data["years_experience"] else None
    if "last_used" in data:
        skill.last_used = datetime.fromisoformat(data["last_used"]) if data["last_used"] else None
    if "certified" in data:
        skill.certified = data["certified"]

    db.commit()
    db.refresh(skill)
    return {"ok": True, "id": skill.id, "skill_name": skill.skill_name}


@router.get("/org-chart")
def get_org_chart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    employees = db.query(EmployeeProfile, User).join(User, EmployeeProfile.user_id == User.id).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.status == EmployeeStatus.ACTIVE
    ).all()

    nodes = {}
    for ep, u in employees:
        nodes[ep.user_id] = {
            "id": ep.id,
            "user_id": ep.user_id,
            "full_name": u.full_name,
            "email": u.email,
            "job_title": ep.job_title,
            "department": ep.department,
            "supervisor_id": ep.supervisor_id,
            "children": [],
        }

    roots = []
    for uid, node in nodes.items():
        sid = node["supervisor_id"]
        if sid and sid in nodes:
            nodes[sid]["children"].append(node)
        else:
            roots.append(node)

    return {"org_chart": roots, "total_employees": len(nodes)}


@router.post("/ai-workforce-analytics")
def ai_workforce_analytics(
    data: dict = Body(default={}),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)

    total_employees = db.query(func.count(EmployeeProfile.id)).filter(EmployeeProfile.org_id == org_id).scalar() or 0

    by_status = {}
    status_rows = db.query(EmployeeProfile.status, func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id
    ).group_by(EmployeeProfile.status).all()
    for s, c in status_rows:
        by_status[s.value if hasattr(s, 'value') else str(s)] = c

    by_department = {}
    dept_rows = db.query(EmployeeProfile.department, func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id, EmployeeProfile.department.isnot(None)
    ).group_by(EmployeeProfile.department).all()
    for d, c in dept_rows:
        by_department[d] = c

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_hours = db.query(
        func.coalesce(func.sum(TimeEntry.total_hours), 0)
    ).filter(TimeEntry.org_id == org_id, TimeEntry.clock_in >= month_start).scalar()

    pending_pto = db.query(func.count(PTORequest.id)).filter(
        PTORequest.org_id == org_id, PTORequest.status == PTOStatus.PENDING
    ).scalar() or 0

    one_year_ago = now - timedelta(days=365)
    terminated = db.query(func.count(EmployeeProfile.id)).filter(
        EmployeeProfile.org_id == org_id,
        EmployeeProfile.status == EmployeeStatus.TERMINATED,
        EmployeeProfile.termination_date.isnot(None),
        EmployeeProfile.termination_date >= one_year_ago
    ).scalar() or 0

    expiry_window = now + timedelta(days=30)
    expiring_certs = db.query(func.count(HRTrainingRecord.id)).filter(
        HRTrainingRecord.org_id == org_id,
        HRTrainingRecord.expiry_date.isnot(None),
        HRTrainingRecord.expiry_date <= expiry_window,
        HRTrainingRecord.expiry_date >= now
    ).scalar() or 0

    question = data.get("question", "Provide a comprehensive workforce analysis with actionable recommendations.")

    data_summary = json.dumps({
        "total_employees": total_employees,
        "by_status": by_status,
        "by_department": by_department,
        "monthly_hours_logged": float(monthly_hours or 0),
        "pending_pto_requests": pending_pto,
        "terminated_last_year": terminated,
        "turnover_rate": round((terminated / total_employees * 100), 1) if total_employees > 0 else 0,
        "expiring_certifications_30_days": expiring_certs,
        "analysis_question": question,
    }, indent=2)

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an HR analytics expert for a fiber optic construction contractor. Analyze workforce data and provide actionable insights on staffing, retention, compliance, training gaps, and operational efficiency. Be specific and data-driven in your recommendations."},
                {"role": "user", "content": f"Analyze this workforce data and answer the following question: {question}\n\nData:\n{data_summary}"}
            ]
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        analysis = f"AI analysis is currently unavailable. Summary: {total_employees} total employees, {terminated} terminated in the last year, {pending_pto} pending PTO requests, {expiring_certs} certifications expiring in 30 days."

    return {
        "analysis": analysis,
        "data_summary": json.loads(data_summary),
    }
