import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    SafetyIncident, SafetyIncidentStatus, SafetyIncidentSeverity,
    SafetyInspectionTemplate, SafetyInspectionRecord,
    ToolboxTalk, ToolboxTalkAttendance,
    SafetyTraining, PPECompliance, CorrectiveAction, CorrectiveActionStatus,
    OSHALog, SafetyDocument, OrgMember, User,
    SafetyRiskAssessment, SafetyScorecard
)

router = APIRouter(prefix="/api/safety", tags=["safety"])


def _get_user_org(db: Session, user: User):
    mem = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not mem:
        raise HTTPException(status_code=403, detail="No org membership")
    return mem.org_id


@router.get("/incidents")
def list_incidents(
    status: str = Query(None),
    severity: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(SafetyIncident).filter(SafetyIncident.org_id == org_id)
    if status:
        q = q.filter(SafetyIncident.status == status)
    if severity:
        q = q.filter(SafetyIncident.severity == severity)
    incidents = q.order_by(desc(SafetyIncident.occurred_at)).all()
    return [{
        "id": i.id,
        "org_id": i.org_id,
        "reported_by": i.reported_by,
        "reporter_name": i.reporter.full_name if i.reporter else None,
        "project_id": i.project_id,
        "project_name": i.project.name if i.project else None,
        "incident_type": i.incident_type,
        "severity": i.severity.value if i.severity else None,
        "status": i.status.value if i.status else None,
        "title": i.title,
        "description": i.description,
        "occurred_at": str(i.occurred_at) if i.occurred_at else None,
        "location_description": i.location_description,
        "location_lat": i.location_lat,
        "location_lng": i.location_lng,
        "is_near_miss": i.is_near_miss,
        "is_osha_recordable": i.is_osha_recordable,
        "days_away": i.days_away,
        "days_restricted": i.days_restricted,
        "medical_treatment": i.medical_treatment,
        "injury_type": i.injury_type,
        "body_part": i.body_part,
        "witnesses": i.witnesses,
        "root_cause": i.root_cause,
        "immediate_actions": i.immediate_actions,
        "photos": i.photos,
        "created_at": str(i.created_at),
        "updated_at": str(i.updated_at),
    } for i in incidents]


@router.post("/incidents")
def create_incident(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    incident = SafetyIncident(
        org_id=org_id,
        reported_by=user.id,
        project_id=data.get("project_id"),
        incident_type=data.get("incident_type", "injury"),
        severity=data.get("severity", "medium"),
        status=data.get("status", "open"),
        title=data["title"],
        description=data.get("description"),
        occurred_at=datetime.fromisoformat(data["occurred_at"]) if data.get("occurred_at") else datetime.utcnow(),
        location_description=data.get("location_description"),
        location_lat=data.get("location_lat"),
        location_lng=data.get("location_lng"),
        is_near_miss=data.get("is_near_miss", False),
        is_osha_recordable=data.get("is_osha_recordable", False),
        days_away=int(data.get("days_away", 0)),
        days_restricted=int(data.get("days_restricted", 0)),
        medical_treatment=data.get("medical_treatment", False),
        injury_type=data.get("injury_type"),
        body_part=data.get("body_part"),
        witnesses=data.get("witnesses"),
        root_cause=data.get("root_cause"),
        immediate_actions=data.get("immediate_actions"),
        photos=data.get("photos"),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return {"ok": True, "id": incident.id}


@router.get("/incidents/stats")
def get_incident_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    by_severity = {}
    sev_rows = db.query(SafetyIncident.severity, func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).group_by(SafetyIncident.severity).all()
    for s, c in sev_rows:
        by_severity[s.value if hasattr(s, 'value') else str(s)] = c

    by_status = {}
    stat_rows = db.query(SafetyIncident.status, func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).group_by(SafetyIncident.status).all()
    for s, c in stat_rows:
        by_status[s.value if hasattr(s, 'value') else str(s)] = c

    near_miss_count = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id, SafetyIncident.is_near_miss == True).scalar() or 0

    osha_recordable_count = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id, SafetyIncident.is_osha_recordable == True).scalar() or 0

    total_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).scalar() or 0

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_count = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id, SafetyIncident.occurred_at >= thirty_days_ago).scalar() or 0

    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    previous_count = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.occurred_at >= sixty_days_ago,
        SafetyIncident.occurred_at < thirty_days_ago
    ).scalar() or 0

    if previous_count > 0:
        trend_pct = round(((recent_count - previous_count) / previous_count) * 100, 1)
    else:
        trend_pct = 0

    return {
        "total_incidents": total_incidents,
        "by_severity": by_severity,
        "by_status": by_status,
        "near_miss_count": near_miss_count,
        "osha_recordable_count": osha_recordable_count,
        "recent_30_days": recent_count,
        "previous_30_days": previous_count,
        "trend_pct": trend_pct,
    }


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    incident = db.query(SafetyIncident).filter(
        SafetyIncident.id == incident_id, SafetyIncident.org_id == org_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    i = incident
    return {
        "id": i.id,
        "org_id": i.org_id,
        "reported_by": i.reported_by,
        "reporter_name": i.reporter.full_name if i.reporter else None,
        "project_id": i.project_id,
        "project_name": i.project.name if i.project else None,
        "incident_type": i.incident_type,
        "severity": i.severity.value if i.severity else None,
        "status": i.status.value if i.status else None,
        "title": i.title,
        "description": i.description,
        "occurred_at": str(i.occurred_at) if i.occurred_at else None,
        "location_description": i.location_description,
        "location_lat": i.location_lat,
        "location_lng": i.location_lng,
        "is_near_miss": i.is_near_miss,
        "is_osha_recordable": i.is_osha_recordable,
        "days_away": i.days_away,
        "days_restricted": i.days_restricted,
        "medical_treatment": i.medical_treatment,
        "injury_type": i.injury_type,
        "body_part": i.body_part,
        "witnesses": i.witnesses,
        "root_cause": i.root_cause,
        "immediate_actions": i.immediate_actions,
        "photos": i.photos,
        "created_at": str(i.created_at),
        "updated_at": str(i.updated_at),
    }


@router.put("/incidents/{incident_id}")
def update_incident(incident_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    incident = db.query(SafetyIncident).filter(
        SafetyIncident.id == incident_id, SafetyIncident.org_id == org_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    fields = ["incident_type", "severity", "status", "title", "description",
              "location_description", "injury_type", "body_part", "witnesses",
              "root_cause", "immediate_actions", "photos", "project_id"]
    for f in fields:
        if f in data:
            setattr(incident, f, data[f])

    bool_fields = ["is_near_miss", "is_osha_recordable", "medical_treatment"]
    for f in bool_fields:
        if f in data:
            setattr(incident, f, data[f])

    int_fields = ["days_away", "days_restricted"]
    for f in int_fields:
        if f in data:
            setattr(incident, f, int(data[f]))

    float_fields = ["location_lat", "location_lng"]
    for f in float_fields:
        if f in data:
            setattr(incident, f, float(data[f]) if data[f] is not None else None)

    if "occurred_at" in data:
        incident.occurred_at = datetime.fromisoformat(data["occurred_at"]) if data["occurred_at"] else None

    db.commit()
    db.refresh(incident)
    return {"ok": True, "id": incident.id}


@router.get("/kpis")
def get_safety_kpis(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    current_year = datetime.utcnow().year
    osha_log = db.query(OSHALog).filter(
        OSHALog.org_id == org_id, OSHALog.year == current_year).first()

    trir = 0.0
    dart_rate = 0.0
    emr = 1.0
    total_hours = 0.0
    recordable = 0
    dart = 0

    if osha_log:
        total_hours = float(osha_log.total_hours_worked or 0)
        recordable = osha_log.recordable_cases or 0
        dart = osha_log.dart_cases or 0
        emr = float(osha_log.emr or 1.0)
        if total_hours > 0:
            trir = round((recordable * 200000) / total_hours, 2)
            dart_rate = round((dart * 200000) / total_hours, 2)

    last_incident = db.query(SafetyIncident).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.is_near_miss == False
    ).order_by(desc(SafetyIncident.occurred_at)).first()

    days_since_last = 0
    if last_incident and last_incident.occurred_at:
        days_since_last = (datetime.utcnow() - last_incident.occurred_at).days

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)

    recent = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id, SafetyIncident.occurred_at >= thirty_days_ago).scalar() or 0
    previous = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.occurred_at >= sixty_days_ago,
        SafetyIncident.occurred_at < thirty_days_ago
    ).scalar() or 0

    if previous > 0:
        incident_trend = round(((recent - previous) / previous) * 100, 1)
    else:
        incident_trend = 0

    total_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).scalar() or 0
    open_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.status.in_(["open", "investigating", "corrective_action"])
    ).scalar() or 0
    near_misses = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id, SafetyIncident.is_near_miss == True).scalar() or 0

    total_training = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id).scalar() or 0
    completed_training = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id, SafetyTraining.status == "completed").scalar() or 0
    training_compliance = round((completed_training / total_training * 100) if total_training > 0 else 100)

    return {
        "trir": trir,
        "dart_rate": dart_rate,
        "emr": emr,
        "days_since_last_incident": days_since_last,
        "incident_trend": incident_trend,
        "total_hours_worked": total_hours,
        "recordable_cases": recordable,
        "dart_cases": dart,
        "current_year": current_year,
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "near_misses": near_misses,
        "training_compliance": training_compliance,
    }


@router.get("/inspection-templates")
def list_inspection_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    templates = db.query(SafetyInspectionTemplate).filter(
        SafetyInspectionTemplate.org_id == org_id).order_by(desc(SafetyInspectionTemplate.created_at)).all()
    return [{
        "id": t.id,
        "org_id": t.org_id,
        "name": t.name,
        "category": t.category,
        "checklist_items": t.checklist_items,
        "frequency": t.frequency,
        "is_active": t.is_active,
        "created_at": str(t.created_at),
    } for t in templates]


@router.post("/inspection-templates")
def create_inspection_template(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    template = SafetyInspectionTemplate(
        org_id=org_id,
        name=data["name"],
        category=data.get("category"),
        checklist_items=data.get("checklist_items"),
        frequency=data.get("frequency", "daily"),
        is_active=data.get("is_active", True),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"ok": True, "id": template.id}


@router.get("/inspections")
def list_inspections(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    records = db.query(SafetyInspectionRecord).filter(
        SafetyInspectionRecord.org_id == org_id).order_by(desc(SafetyInspectionRecord.conducted_at)).all()
    return [{
        "id": r.id,
        "org_id": r.org_id,
        "template_id": r.template_id,
        "template_name": r.template.name if r.template else None,
        "inspector_id": r.inspector_id,
        "inspector_name": r.inspector.full_name if r.inspector else None,
        "project_id": r.project_id,
        "project_name": r.project.name if r.project else None,
        "status": r.status,
        "checklist_results": r.checklist_results,
        "score": float(r.score) if r.score is not None else None,
        "findings": r.findings,
        "conducted_at": str(r.conducted_at) if r.conducted_at else None,
        "location_description": r.location_description,
        "photos": r.photos,
        "created_at": str(r.created_at),
    } for r in records]


@router.post("/inspections")
def create_inspection(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    record = SafetyInspectionRecord(
        org_id=org_id,
        template_id=data.get("template_id"),
        inspector_id=user.id,
        project_id=data.get("project_id"),
        status=data.get("status", "completed"),
        checklist_results=data.get("checklist_results"),
        score=float(data["score"]) if data.get("score") is not None else None,
        findings=data.get("findings"),
        conducted_at=datetime.fromisoformat(data["conducted_at"]) if data.get("conducted_at") else datetime.utcnow(),
        location_description=data.get("location_description"),
        photos=data.get("photos"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


@router.get("/toolbox-talks")
def list_toolbox_talks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    talks = db.query(ToolboxTalk).filter(
        ToolboxTalk.org_id == org_id).order_by(desc(ToolboxTalk.conducted_at)).all()
    return [{
        "id": t.id,
        "org_id": t.org_id,
        "presenter_id": t.presenter_id,
        "presenter_name": t.presenter.full_name if t.presenter else None,
        "project_id": t.project_id,
        "project_name": t.project.name if t.project else None,
        "topic": t.topic,
        "category": t.category,
        "content": t.content,
        "duration_minutes": t.duration_minutes,
        "conducted_at": str(t.conducted_at) if t.conducted_at else None,
        "attendee_count": t.attendee_count,
        "notes": t.notes,
        "created_at": str(t.created_at),
        "attendance": [{
            "id": a.id,
            "user_id": a.user_id,
            "user_name": a.user.full_name if a.user else None,
            "attended": a.attended,
            "signature": a.signature,
        } for a in (t.attendance or [])],
    } for t in talks]


@router.post("/toolbox-talks")
def create_toolbox_talk(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    talk = ToolboxTalk(
        org_id=org_id,
        presenter_id=data.get("presenter_id", user.id),
        project_id=data.get("project_id"),
        topic=data["topic"],
        category=data.get("category"),
        content=data.get("content"),
        duration_minutes=int(data.get("duration_minutes", 15)),
        conducted_at=datetime.fromisoformat(data["conducted_at"]) if data.get("conducted_at") else datetime.utcnow(),
        attendee_count=int(data.get("attendee_count", 0)),
        notes=data.get("notes"),
    )
    db.add(talk)
    db.commit()
    db.refresh(talk)
    return {"ok": True, "id": talk.id}


@router.post("/toolbox-talks/{talk_id}/attendance")
def add_toolbox_talk_attendance(talk_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    talk = db.query(ToolboxTalk).filter(ToolboxTalk.id == talk_id, ToolboxTalk.org_id == org_id).first()
    if not talk:
        raise HTTPException(status_code=404, detail="Toolbox talk not found")

    user_id = data.get("user_id", user.id)
    existing = db.query(ToolboxTalkAttendance).filter(
        ToolboxTalkAttendance.talk_id == talk_id,
        ToolboxTalkAttendance.user_id == user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Attendance already recorded for this user")

    attendance = ToolboxTalkAttendance(
        talk_id=talk_id,
        user_id=user_id,
        attended=data.get("attended", True),
        signature=data.get("signature"),
    )
    db.add(attendance)
    talk.attendee_count = (talk.attendee_count or 0) + 1
    db.commit()
    return {"ok": True, "id": attendance.id}


@router.get("/trainings")
def list_trainings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    trainings = db.query(SafetyTraining).filter(
        SafetyTraining.org_id == org_id).order_by(desc(SafetyTraining.completion_date)).all()
    return [{
        "id": t.id,
        "org_id": t.org_id,
        "user_id": t.user_id,
        "user_name": t.user.full_name if t.user else None,
        "training_name": t.training_name,
        "training_type": t.training_type,
        "provider": t.provider,
        "completion_date": str(t.completion_date) if t.completion_date else None,
        "expiry_date": str(t.expiry_date) if t.expiry_date else None,
        "certificate_number": t.certificate_number,
        "status": t.status,
        "score": float(t.score) if t.score is not None else None,
        "hours": float(t.hours) if t.hours is not None else None,
        "notes": t.notes,
        "created_at": str(t.created_at),
    } for t in trainings]


@router.post("/trainings")
def create_training(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    training = SafetyTraining(
        org_id=org_id,
        user_id=data.get("user_id", user.id),
        training_name=data["training_name"],
        training_type=data.get("training_type"),
        provider=data.get("provider"),
        completion_date=datetime.fromisoformat(data["completion_date"]) if data.get("completion_date") else datetime.utcnow(),
        expiry_date=datetime.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None,
        certificate_number=data.get("certificate_number"),
        status=data.get("status", "completed"),
        score=float(data["score"]) if data.get("score") is not None else None,
        hours=float(data["hours"]) if data.get("hours") is not None else None,
        notes=data.get("notes"),
    )
    db.add(training)
    db.commit()
    db.refresh(training)
    return {"ok": True, "id": training.id}


@router.get("/trainings/expiring")
def list_expiring_trainings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cutoff = datetime.utcnow() + timedelta(days=30)
    trainings = db.query(SafetyTraining).filter(
        SafetyTraining.org_id == org_id,
        SafetyTraining.expiry_date.isnot(None),
        SafetyTraining.expiry_date <= cutoff
    ).order_by(SafetyTraining.expiry_date).all()
    return [{
        "id": t.id,
        "user_id": t.user_id,
        "user_name": t.user.full_name if t.user else None,
        "training_name": t.training_name,
        "training_type": t.training_type,
        "expiry_date": str(t.expiry_date) if t.expiry_date else None,
        "status": t.status,
        "days_until_expiry": (t.expiry_date - datetime.utcnow()).days if t.expiry_date else None,
    } for t in trainings]


@router.get("/ppe")
def list_ppe(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    records = db.query(PPECompliance).filter(
        PPECompliance.org_id == org_id).order_by(desc(PPECompliance.updated_at)).all()
    return [{
        "id": r.id,
        "org_id": r.org_id,
        "user_id": r.user_id,
        "user_name": r.user.full_name if r.user else None,
        "ppe_type": r.ppe_type,
        "status": r.status,
        "issued_at": str(r.issued_at) if r.issued_at else None,
        "last_inspected_at": str(r.last_inspected_at) if r.last_inspected_at else None,
        "next_inspection_due": str(r.next_inspection_due) if r.next_inspection_due else None,
        "condition": r.condition,
        "serial_number": r.serial_number,
        "notes": r.notes,
        "created_at": str(r.created_at),
        "updated_at": str(r.updated_at),
    } for r in records]


@router.post("/ppe")
def create_ppe(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ppe = PPECompliance(
        org_id=org_id,
        user_id=data.get("user_id", user.id),
        ppe_type=data["ppe_type"],
        status=data.get("status", "compliant"),
        issued_at=datetime.fromisoformat(data["issued_at"]) if data.get("issued_at") else datetime.utcnow(),
        last_inspected_at=datetime.fromisoformat(data["last_inspected_at"]) if data.get("last_inspected_at") else None,
        next_inspection_due=datetime.fromisoformat(data["next_inspection_due"]) if data.get("next_inspection_due") else None,
        condition=data.get("condition", "good"),
        serial_number=data.get("serial_number"),
        notes=data.get("notes"),
    )
    db.add(ppe)
    db.commit()
    db.refresh(ppe)
    return {"ok": True, "id": ppe.id}


@router.put("/ppe/{ppe_id}")
def update_ppe(ppe_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    ppe = db.query(PPECompliance).filter(PPECompliance.id == ppe_id, PPECompliance.org_id == org_id).first()
    if not ppe:
        raise HTTPException(status_code=404, detail="PPE record not found")

    fields = ["ppe_type", "status", "condition", "serial_number", "notes"]
    for f in fields:
        if f in data:
            setattr(ppe, f, data[f])

    date_fields = ["issued_at", "last_inspected_at", "next_inspection_due"]
    for f in date_fields:
        if f in data:
            setattr(ppe, f, datetime.fromisoformat(data[f]) if data[f] else None)

    db.commit()
    db.refresh(ppe)
    return {"ok": True, "id": ppe.id}


@router.get("/corrective-actions")
def list_corrective_actions(
    status: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(CorrectiveAction).filter(CorrectiveAction.org_id == org_id)
    if status:
        q = q.filter(CorrectiveAction.status == status)
    actions = q.order_by(desc(CorrectiveAction.created_at)).all()
    return [{
        "id": a.id,
        "org_id": a.org_id,
        "incident_id": a.incident_id,
        "inspection_id": a.inspection_id,
        "assigned_to": a.assigned_to,
        "assignee_name": a.assignee.full_name if a.assignee else None,
        "title": a.title,
        "description": a.description,
        "action_type": a.action_type,
        "priority": a.priority,
        "status": a.status.value if a.status else None,
        "due_date": str(a.due_date) if a.due_date else None,
        "completed_at": str(a.completed_at) if a.completed_at else None,
        "verified_by": a.verified_by,
        "verifier_name": a.verifier.full_name if a.verifier else None,
        "verified_at": str(a.verified_at) if a.verified_at else None,
        "root_cause_category": a.root_cause_category,
        "notes": a.notes,
        "created_at": str(a.created_at),
        "updated_at": str(a.updated_at),
    } for a in actions]


@router.post("/corrective-actions")
def create_corrective_action(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    action = CorrectiveAction(
        org_id=org_id,
        incident_id=data.get("incident_id"),
        inspection_id=data.get("inspection_id"),
        assigned_to=data.get("assigned_to"),
        title=data["title"],
        description=data.get("description"),
        action_type=data.get("action_type", "corrective"),
        priority=data.get("priority", "medium"),
        status=data.get("status", "open"),
        due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
        root_cause_category=data.get("root_cause_category"),
        notes=data.get("notes"),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return {"ok": True, "id": action.id}


@router.put("/corrective-actions/{action_id}")
def update_corrective_action(action_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    action = db.query(CorrectiveAction).filter(
        CorrectiveAction.id == action_id, CorrectiveAction.org_id == org_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Corrective action not found")

    fields = ["title", "description", "action_type", "priority", "status",
              "root_cause_category", "notes", "assigned_to", "incident_id", "inspection_id"]
    for f in fields:
        if f in data:
            setattr(action, f, data[f])

    if "due_date" in data:
        action.due_date = datetime.fromisoformat(data["due_date"]) if data["due_date"] else None

    if data.get("status") == "completed" and not action.completed_at:
        action.completed_at = datetime.utcnow()

    if data.get("status") == "verified":
        action.verified_by = user.id
        action.verified_at = datetime.utcnow()

    db.commit()
    db.refresh(action)
    return {"ok": True, "id": action.id}


@router.get("/osha-logs")
def list_osha_logs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    logs = db.query(OSHALog).filter(OSHALog.org_id == org_id).order_by(desc(OSHALog.year)).all()
    return [{
        "id": l.id,
        "org_id": l.org_id,
        "year": l.year,
        "total_hours_worked": float(l.total_hours_worked or 0),
        "total_employees": l.total_employees or 0,
        "total_incidents": l.total_incidents or 0,
        "recordable_cases": l.recordable_cases or 0,
        "dart_cases": l.dart_cases or 0,
        "fatalities": l.fatalities or 0,
        "trir": float(l.trir or 0),
        "dart_rate": float(l.dart_rate or 0),
        "emr": float(l.emr or 1.0),
        "days_away": l.days_away or 0,
        "days_restricted": l.days_restricted or 0,
        "notes": l.notes,
        "created_at": str(l.created_at),
        "updated_at": str(l.updated_at),
    } for l in logs]


@router.post("/osha-logs")
def create_osha_log(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    total_hours = float(data.get("total_hours_worked", 0))
    recordable = int(data.get("recordable_cases", 0))
    dart = int(data.get("dart_cases", 0))
    trir = round((recordable * 200000) / total_hours, 2) if total_hours > 0 else 0
    dart_rate = round((dart * 200000) / total_hours, 2) if total_hours > 0 else 0

    existing = db.query(OSHALog).filter(
        OSHALog.org_id == org_id, OSHALog.year == int(data["year"])).first()
    if existing:
        existing.total_hours_worked = total_hours
        existing.total_employees = int(data.get("total_employees", 0))
        existing.total_incidents = int(data.get("total_incidents", 0))
        existing.recordable_cases = recordable
        existing.dart_cases = dart
        existing.fatalities = int(data.get("fatalities", 0))
        existing.trir = trir
        existing.dart_rate = dart_rate
        existing.emr = float(data.get("emr", 1.0))
        existing.days_away = int(data.get("days_away", 0))
        existing.days_restricted = int(data.get("days_restricted", 0))
        existing.notes = data.get("notes")
        db.commit()
        return {"ok": True, "id": existing.id, "updated": True}

    log = OSHALog(
        org_id=org_id,
        year=int(data["year"]),
        total_hours_worked=total_hours,
        total_employees=int(data.get("total_employees", 0)),
        total_incidents=int(data.get("total_incidents", 0)),
        recordable_cases=recordable,
        dart_cases=dart,
        fatalities=int(data.get("fatalities", 0)),
        trir=trir,
        dart_rate=dart_rate,
        emr=float(data.get("emr", 1.0)),
        days_away=int(data.get("days_away", 0)),
        days_restricted=int(data.get("days_restricted", 0)),
        notes=data.get("notes"),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"ok": True, "id": log.id}


@router.get("/documents")
def list_safety_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    docs = db.query(SafetyDocument).filter(
        SafetyDocument.org_id == org_id).order_by(desc(SafetyDocument.updated_at)).all()
    return [{
        "id": d.id,
        "org_id": d.org_id,
        "title": d.title,
        "category": d.category,
        "description": d.description,
        "file_path": d.file_path,
        "file_type": d.file_type,
        "version": d.version,
        "effective_date": str(d.effective_date) if d.effective_date else None,
        "review_date": str(d.review_date) if d.review_date else None,
        "uploaded_by": d.uploaded_by,
        "uploader_name": d.uploader.full_name if d.uploader else None,
        "is_active": d.is_active,
        "created_at": str(d.created_at),
        "updated_at": str(d.updated_at),
    } for d in docs]


@router.post("/documents")
def create_safety_document(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    doc = SafetyDocument(
        org_id=org_id,
        title=data["title"],
        category=data.get("category"),
        description=data.get("description"),
        file_path=data.get("file_path"),
        file_type=data.get("file_type"),
        version=data.get("version", "1.0"),
        effective_date=datetime.fromisoformat(data["effective_date"]) if data.get("effective_date") else None,
        review_date=datetime.fromisoformat(data["review_date"]) if data.get("review_date") else None,
        uploaded_by=user.id,
        is_active=data.get("is_active", True),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"ok": True, "id": doc.id}


@router.post("/ai-risk-analysis")
def ai_risk_analysis(data: dict = Body(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    total_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).scalar() or 0

    by_severity = {}
    sev_rows = db.query(SafetyIncident.severity, func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).group_by(SafetyIncident.severity).all()
    for s, c in sev_rows:
        by_severity[s.value if hasattr(s, 'value') else str(s)] = c

    by_type = {}
    type_rows = db.query(SafetyIncident.incident_type, func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id).group_by(SafetyIncident.incident_type).all()
    for t, c in type_rows:
        by_type[t] = c

    open_actions = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.status.in_(["open", "in_progress"])
    ).scalar() or 0

    overdue_actions = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.due_date < datetime.utcnow(),
        CorrectiveAction.status.in_(["open", "in_progress"])
    ).scalar() or 0

    near_miss_count = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id, SafetyIncident.is_near_miss == True).scalar() or 0

    current_year = datetime.utcnow().year
    osha_log = db.query(OSHALog).filter(
        OSHALog.org_id == org_id, OSHALog.year == current_year).first()

    recent_incidents = db.query(SafetyIncident).filter(
        SafetyIncident.org_id == org_id).order_by(desc(SafetyIncident.occurred_at)).limit(10).all()
    recent_data = [{"title": i.title, "type": i.incident_type,
                    "severity": i.severity.value if i.severity else "unknown",
                    "root_cause": i.root_cause} for i in recent_incidents]

    data_summary = json.dumps({
        "total_incidents": total_incidents,
        "by_severity": by_severity,
        "by_type": by_type,
        "open_corrective_actions": open_actions,
        "overdue_corrective_actions": overdue_actions,
        "near_miss_count": near_miss_count,
        "osha_trir": float(osha_log.trir) if osha_log else None,
        "osha_dart": float(osha_log.dart_rate) if osha_log else None,
        "osha_emr": float(osha_log.emr) if osha_log else None,
        "recent_incidents": recent_data,
    }, indent=2)

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a safety analytics expert for fiber optic construction contractors. Analyze the safety data provided and give actionable insights including: top risk areas, trends, recommendations for reducing incidents, OSHA compliance observations, and priority corrective actions. Format your response as structured JSON with keys: risk_summary, top_risks (array), recommendations (array), compliance_notes, priority_actions (array)."},
                {"role": "user", "content": data_summary}
            ]
        )
        analysis = response.choices[0].message.content
        try:
            analysis_json = json.loads(analysis)
        except (json.JSONDecodeError, TypeError):
            analysis_json = {"raw_analysis": analysis}

        return {
            "analysis": analysis_json,
            "data_summary": json.loads(data_summary),
        }
    except Exception as e:
        return {
            "analysis": {
                "risk_summary": "AI analysis unavailable. Please review your safety data manually.",
                "error": str(e),
                "top_risks": [],
                "recommendations": ["Review incident trends manually", "Ensure all corrective actions are addressed"],
                "compliance_notes": "Unable to generate automated compliance analysis.",
                "priority_actions": [],
            },
            "data_summary": json.loads(data_summary),
        }


@router.get("/risk-assessments")
def list_risk_assessments(
    status: str = Query(None),
    project_id: str = Query(None),
    risk_level: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(SafetyRiskAssessment).filter(SafetyRiskAssessment.org_id == org_id)
    if status:
        q = q.filter(SafetyRiskAssessment.status == status)
    if project_id:
        q = q.filter(SafetyRiskAssessment.project_id == project_id)
    if risk_level:
        q = q.filter(SafetyRiskAssessment.risk_level == risk_level)
    assessments = q.order_by(desc(SafetyRiskAssessment.created_at)).all()
    return [{
        "id": a.id,
        "org_id": a.org_id,
        "project_id": a.project_id,
        "project_name": a.project.name if a.project else None,
        "title": a.title,
        "description": a.description,
        "location": a.location,
        "assessment_date": str(a.assessment_date) if a.assessment_date else None,
        "risk_level": a.risk_level,
        "likelihood": a.likelihood,
        "severity": a.severity,
        "risk_score": a.risk_score,
        "hazard_type": a.hazard_type,
        "control_measures": a.control_measures,
        "residual_risk_level": a.residual_risk_level,
        "residual_risk_score": a.residual_risk_score,
        "assigned_to": a.assigned_to,
        "assignee_name": a.assignee.full_name if a.assignee else None,
        "reviewed_by": a.reviewed_by,
        "reviewer_name": a.reviewer.full_name if a.reviewer else None,
        "review_date": str(a.review_date) if a.review_date else None,
        "next_review_date": str(a.next_review_date) if a.next_review_date else None,
        "status": a.status,
        "created_by": a.created_by,
        "creator_name": a.creator.full_name if a.creator else None,
        "created_at": str(a.created_at),
        "updated_at": str(a.updated_at),
    } for a in assessments]


@router.post("/risk-assessments")
def create_risk_assessment(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    likelihood = int(data.get("likelihood", 3))
    severity_val = int(data.get("severity", 3))
    risk_score = likelihood * severity_val
    risk_level = data.get("risk_level", "medium")
    if not data.get("risk_level"):
        if risk_score >= 15:
            risk_level = "critical"
        elif risk_score >= 10:
            risk_level = "high"
        elif risk_score >= 5:
            risk_level = "medium"
        else:
            risk_level = "low"
    assessment = SafetyRiskAssessment(
        org_id=org_id,
        project_id=data.get("project_id"),
        title=data["title"],
        description=data.get("description"),
        location=data.get("location"),
        assessment_date=datetime.fromisoformat(data["assessment_date"]) if data.get("assessment_date") else datetime.utcnow(),
        risk_level=risk_level,
        likelihood=likelihood,
        severity=severity_val,
        risk_score=risk_score,
        hazard_type=data.get("hazard_type"),
        control_measures=data.get("control_measures"),
        residual_risk_level=data.get("residual_risk_level"),
        residual_risk_score=int(data["residual_risk_score"]) if data.get("residual_risk_score") is not None else None,
        assigned_to=data.get("assigned_to"),
        status=data.get("status", "open"),
        next_review_date=datetime.fromisoformat(data["next_review_date"]) if data.get("next_review_date") else None,
        created_by=user.id,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return {"ok": True, "id": assessment.id}


@router.get("/risk-assessments/{assessment_id}")
def get_risk_assessment(assessment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    a = db.query(SafetyRiskAssessment).filter(
        SafetyRiskAssessment.id == assessment_id, SafetyRiskAssessment.org_id == org_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return {
        "id": a.id,
        "org_id": a.org_id,
        "project_id": a.project_id,
        "project_name": a.project.name if a.project else None,
        "title": a.title,
        "description": a.description,
        "location": a.location,
        "assessment_date": str(a.assessment_date) if a.assessment_date else None,
        "risk_level": a.risk_level,
        "likelihood": a.likelihood,
        "severity": a.severity,
        "risk_score": a.risk_score,
        "hazard_type": a.hazard_type,
        "control_measures": a.control_measures,
        "residual_risk_level": a.residual_risk_level,
        "residual_risk_score": a.residual_risk_score,
        "assigned_to": a.assigned_to,
        "assignee_name": a.assignee.full_name if a.assignee else None,
        "reviewed_by": a.reviewed_by,
        "reviewer_name": a.reviewer.full_name if a.reviewer else None,
        "review_date": str(a.review_date) if a.review_date else None,
        "next_review_date": str(a.next_review_date) if a.next_review_date else None,
        "status": a.status,
        "created_by": a.created_by,
        "creator_name": a.creator.full_name if a.creator else None,
        "created_at": str(a.created_at),
        "updated_at": str(a.updated_at),
    }


@router.put("/risk-assessments/{assessment_id}")
def update_risk_assessment(assessment_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    assessment = db.query(SafetyRiskAssessment).filter(
        SafetyRiskAssessment.id == assessment_id, SafetyRiskAssessment.org_id == org_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")

    fields = ["title", "description", "location", "risk_level", "hazard_type",
              "control_measures", "residual_risk_level", "status", "assigned_to", "project_id"]
    for f in fields:
        if f in data:
            setattr(assessment, f, data[f])

    int_fields = ["likelihood", "severity", "risk_score", "residual_risk_score"]
    for f in int_fields:
        if f in data:
            setattr(assessment, f, int(data[f]) if data[f] is not None else None)

    if "likelihood" in data or "severity" in data:
        assessment.risk_score = (assessment.likelihood or 1) * (assessment.severity or 1)

    date_fields = ["assessment_date", "next_review_date"]
    for f in date_fields:
        if f in data:
            setattr(assessment, f, datetime.fromisoformat(data[f]) if data[f] else None)

    db.commit()
    db.refresh(assessment)
    return {"ok": True, "id": assessment.id}


@router.post("/risk-assessments/{assessment_id}/review")
def review_risk_assessment(assessment_id: str, data: dict = Body(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    assessment = db.query(SafetyRiskAssessment).filter(
        SafetyRiskAssessment.id == assessment_id, SafetyRiskAssessment.org_id == org_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")

    assessment.reviewed_by = user.id
    assessment.review_date = datetime.utcnow()
    assessment.status = "reviewed"
    if data and data.get("next_review_date"):
        assessment.next_review_date = datetime.fromisoformat(data["next_review_date"])
    if data and data.get("notes"):
        assessment.control_measures = data["notes"]

    db.commit()
    db.refresh(assessment)
    return {"ok": True, "id": assessment.id}


@router.get("/scorecards")
def list_scorecards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    scorecards = db.query(SafetyScorecard).filter(
        SafetyScorecard.org_id == org_id).order_by(desc(SafetyScorecard.period_end)).all()
    return [{
        "id": s.id,
        "org_id": s.org_id,
        "period_start": str(s.period_start) if s.period_start else None,
        "period_end": str(s.period_end) if s.period_end else None,
        "total_hours_worked": float(s.total_hours_worked or 0),
        "total_incidents": s.total_incidents or 0,
        "recordable_incidents": s.recordable_incidents or 0,
        "lost_time_incidents": s.lost_time_incidents or 0,
        "near_misses": s.near_misses or 0,
        "first_aid_cases": s.first_aid_cases or 0,
        "trir": float(s.trir or 0),
        "dart_rate": float(s.dart_rate or 0),
        "emr": float(s.emr or 1.0),
        "severity_rate": float(s.severity_rate or 0),
        "training_compliance_pct": float(s.training_compliance_pct or 0),
        "inspection_completion_pct": float(s.inspection_completion_pct or 0),
        "corrective_action_closure_pct": float(s.corrective_action_closure_pct or 0),
        "safety_score": float(s.safety_score or 0),
        "grade": s.grade,
        "notes": s.notes,
        "created_by": s.created_by,
        "creator_name": s.creator.full_name if s.creator else None,
        "created_at": str(s.created_at),
    } for s in scorecards]


@router.post("/scorecards/generate")
def generate_scorecard(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    period_start = datetime.fromisoformat(data["period_start"])
    period_end = datetime.fromisoformat(data["period_end"])

    total_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.occurred_at >= period_start,
        SafetyIncident.occurred_at <= period_end
    ).scalar() or 0

    recordable_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.is_osha_recordable == True,
        SafetyIncident.occurred_at >= period_start,
        SafetyIncident.occurred_at <= period_end
    ).scalar() or 0

    near_misses = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.is_near_miss == True,
        SafetyIncident.occurred_at >= period_start,
        SafetyIncident.occurred_at <= period_end
    ).scalar() or 0

    dart_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.is_osha_recordable == True,
        SafetyIncident.occurred_at >= period_start,
        SafetyIncident.occurred_at <= period_end,
        (SafetyIncident.days_away > 0) | (SafetyIncident.days_restricted > 0)
    ).scalar() or 0

    lost_time_incidents = db.query(func.count(SafetyIncident.id)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.occurred_at >= period_start,
        SafetyIncident.occurred_at <= period_end,
        SafetyIncident.days_away > 0
    ).scalar() or 0

    first_aid_cases = total_incidents - recordable_incidents

    current_year = period_end.year
    osha_log = db.query(OSHALog).filter(
        OSHALog.org_id == org_id, OSHALog.year == current_year).first()
    total_hours = float(osha_log.total_hours_worked) if osha_log and osha_log.total_hours_worked else 0
    emr = float(osha_log.emr) if osha_log and osha_log.emr else 1.0

    trir = round((recordable_incidents * 200000) / total_hours, 2) if total_hours > 0 else 0
    dart_rate = round((dart_incidents * 200000) / total_hours, 2) if total_hours > 0 else 0

    total_days = db.query(func.coalesce(func.sum(SafetyIncident.days_away), 0) + func.coalesce(func.sum(SafetyIncident.days_restricted), 0)).filter(
        SafetyIncident.org_id == org_id,
        SafetyIncident.occurred_at >= period_start,
        SafetyIncident.occurred_at <= period_end
    ).scalar() or 0
    severity_rate = round((int(total_days) * 200000) / total_hours, 2) if total_hours > 0 else 0

    total_training = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id).scalar() or 0
    completed_training = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id, SafetyTraining.status == "completed").scalar() or 0
    training_compliance_pct = round((completed_training / total_training * 100) if total_training > 0 else 100, 1)

    total_inspections = db.query(func.count(SafetyInspectionRecord.id)).filter(
        SafetyInspectionRecord.org_id == org_id,
        SafetyInspectionRecord.conducted_at >= period_start,
        SafetyInspectionRecord.conducted_at <= period_end
    ).scalar() or 0
    completed_inspections = db.query(func.count(SafetyInspectionRecord.id)).filter(
        SafetyInspectionRecord.org_id == org_id,
        SafetyInspectionRecord.status == "completed",
        SafetyInspectionRecord.conducted_at >= period_start,
        SafetyInspectionRecord.conducted_at <= period_end
    ).scalar() or 0
    inspection_completion_pct = round((completed_inspections / total_inspections * 100) if total_inspections > 0 else 100, 1)

    total_actions = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.created_at >= period_start,
        CorrectiveAction.created_at <= period_end
    ).scalar() or 0
    closed_actions = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.created_at >= period_start,
        CorrectiveAction.created_at <= period_end,
        CorrectiveAction.status.in_(["completed", "verified", "closed"])
    ).scalar() or 0
    corrective_action_closure_pct = round((closed_actions / total_actions * 100) if total_actions > 0 else 100, 1)

    safety_score = round(
        (training_compliance_pct * 0.30) +
        (inspection_completion_pct * 0.30) +
        (corrective_action_closure_pct * 0.25) +
        (max(0, 100 - (trir * 10)) * 0.15),
        1
    )

    if safety_score >= 90:
        grade = "A"
    elif safety_score >= 80:
        grade = "B"
    elif safety_score >= 70:
        grade = "C"
    elif safety_score >= 60:
        grade = "D"
    else:
        grade = "F"

    scorecard = SafetyScorecard(
        org_id=org_id,
        period_start=period_start,
        period_end=period_end,
        total_hours_worked=total_hours,
        total_incidents=total_incidents,
        recordable_incidents=recordable_incidents,
        lost_time_incidents=lost_time_incidents,
        near_misses=near_misses,
        first_aid_cases=first_aid_cases if first_aid_cases > 0 else 0,
        trir=trir,
        dart_rate=dart_rate,
        emr=emr,
        severity_rate=severity_rate,
        training_compliance_pct=training_compliance_pct,
        inspection_completion_pct=inspection_completion_pct,
        corrective_action_closure_pct=corrective_action_closure_pct,
        safety_score=safety_score,
        grade=grade,
        notes=data.get("notes"),
        created_by=user.id,
    )
    db.add(scorecard)
    db.commit()
    db.refresh(scorecard)
    return {
        "ok": True,
        "id": scorecard.id,
        "safety_score": safety_score,
        "grade": grade,
        "trir": trir,
        "dart_rate": dart_rate,
        "emr": emr,
        "training_compliance_pct": training_compliance_pct,
        "inspection_completion_pct": inspection_completion_pct,
        "corrective_action_closure_pct": corrective_action_closure_pct,
    }


@router.get("/scorecards/{scorecard_id}")
def get_scorecard(scorecard_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    s = db.query(SafetyScorecard).filter(
        SafetyScorecard.id == scorecard_id, SafetyScorecard.org_id == org_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    return {
        "id": s.id,
        "org_id": s.org_id,
        "period_start": str(s.period_start) if s.period_start else None,
        "period_end": str(s.period_end) if s.period_end else None,
        "total_hours_worked": float(s.total_hours_worked or 0),
        "total_incidents": s.total_incidents or 0,
        "recordable_incidents": s.recordable_incidents or 0,
        "lost_time_incidents": s.lost_time_incidents or 0,
        "near_misses": s.near_misses or 0,
        "first_aid_cases": s.first_aid_cases or 0,
        "trir": float(s.trir or 0),
        "dart_rate": float(s.dart_rate or 0),
        "emr": float(s.emr or 1.0),
        "severity_rate": float(s.severity_rate or 0),
        "training_compliance_pct": float(s.training_compliance_pct or 0),
        "inspection_completion_pct": float(s.inspection_completion_pct or 0),
        "corrective_action_closure_pct": float(s.corrective_action_closure_pct or 0),
        "safety_score": float(s.safety_score or 0),
        "grade": s.grade,
        "notes": s.notes,
        "created_by": s.created_by,
        "creator_name": s.creator.full_name if s.creator else None,
        "created_at": str(s.created_at),
    }


@router.get("/compliance-dashboard")
def get_compliance_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    now = datetime.utcnow()

    overdue_trainings = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id,
        SafetyTraining.expiry_date < now,
        SafetyTraining.status != "completed"
    ).scalar() or 0

    expired_certifications = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id,
        SafetyTraining.expiry_date < now,
        SafetyTraining.status == "completed"
    ).scalar() or 0

    expiring_soon = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id,
        SafetyTraining.expiry_date >= now,
        SafetyTraining.expiry_date <= now + timedelta(days=30)
    ).scalar() or 0

    overdue_inspections = db.query(func.count(SafetyInspectionRecord.id)).filter(
        SafetyInspectionRecord.org_id == org_id,
        SafetyInspectionRecord.status.in_(["pending", "in_progress", "scheduled"])
    ).scalar() or 0

    open_corrective_actions = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.status.in_(["open", "in_progress"])
    ).scalar() or 0

    overdue_corrective_actions = db.query(func.count(CorrectiveAction.id)).filter(
        CorrectiveAction.org_id == org_id,
        CorrectiveAction.due_date < now,
        CorrectiveAction.status.in_(["open", "in_progress"])
    ).scalar() or 0

    ppe_non_compliant = db.query(func.count(PPECompliance.id)).filter(
        PPECompliance.org_id == org_id,
        PPECompliance.status != "compliant"
    ).scalar() or 0

    total_training = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id).scalar() or 0
    completed_training = db.query(func.count(SafetyTraining.id)).filter(
        SafetyTraining.org_id == org_id, SafetyTraining.status == "completed").scalar() or 0
    training_compliance_pct = round((completed_training / total_training * 100) if total_training > 0 else 100, 1)

    open_risk_assessments = db.query(func.count(SafetyRiskAssessment.id)).filter(
        SafetyRiskAssessment.org_id == org_id,
        SafetyRiskAssessment.status == "open"
    ).scalar() or 0

    return {
        "overdue_trainings": overdue_trainings,
        "expired_certifications": expired_certifications,
        "expiring_certifications_30_days": expiring_soon,
        "overdue_inspections": overdue_inspections,
        "open_corrective_actions": open_corrective_actions,
        "overdue_corrective_actions": overdue_corrective_actions,
        "ppe_non_compliant_count": ppe_non_compliant,
        "training_compliance_pct": training_compliance_pct,
        "open_risk_assessments": open_risk_assessments,
    }
