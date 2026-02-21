import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    Asset, AssetStatus, AssetCategory, AssetAllocation, AssetIncident,
    AssetMaintenance, User, OrgMember, Crew, Project, FleetVehicle
)

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _get_user_org(db: Session, user: User):
    mem = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not mem:
        raise HTTPException(status_code=403, detail="No org membership")
    return mem.org_id


def _serialize_asset(a):
    return {
        "id": a.id,
        "org_id": a.org_id,
        "category_id": a.category_id,
        "category_name": a.category.name if a.category else None,
        "category_color": a.category.color if a.category else "#6B7280",
        "name": a.name,
        "asset_tag": a.asset_tag,
        "serial_number": a.serial_number,
        "make": a.make,
        "model": a.model,
        "description": a.description,
        "status": a.status.value if a.status else "available",
        "condition": a.condition,
        "purchase_date": str(a.purchase_date) if a.purchase_date else None,
        "purchase_cost": float(a.purchase_cost or 0),
        "current_value": float(a.current_value or 0),
        "depreciation_method": a.depreciation_method,
        "depreciation_rate": float(a.depreciation_rate or 0),
        "useful_life_years": float(a.useful_life_years or 5),
        "salvage_value": float(a.salvage_value or 0),
        "warranty_expiry": str(a.warranty_expiry) if a.warranty_expiry else None,
        "location_description": a.location_description,
        "assigned_to_user_id": a.assigned_to_user_id,
        "assigned_user_name": a.assigned_user.full_name if a.assigned_user else None,
        "assigned_to_crew_id": a.assigned_to_crew_id,
        "assigned_crew_name": a.assigned_crew.name if a.assigned_crew else None,
        "assigned_to_project_id": a.assigned_to_project_id,
        "assigned_project_name": a.assigned_project.name if a.assigned_project else None,
        "image_url": a.image_url,
        "notes": a.notes,
        "allocation_count": len(a.allocations) if a.allocations else 0,
        "incident_count": len(a.incidents) if a.incidents else 0,
        "maintenance_count": len(a.maintenance_records) if a.maintenance_records else 0,
        "created_at": str(a.created_at),
        "updated_at": str(a.updated_at),
    }


@router.get("/categories")
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cats = db.query(AssetCategory).filter(AssetCategory.org_id == org_id).order_by(AssetCategory.name).all()
    return [{"id": c.id, "name": c.name, "description": c.description, "icon": c.icon, "color": c.color,
             "asset_count": len(c.assets) if c.assets else 0} for c in cats]


@router.post("/categories")
def create_category(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    cat = AssetCategory(
        org_id=org_id,
        name=data["name"],
        description=data.get("description"),
        icon=data.get("icon"),
        color=data.get("color", "#3B82F6"),
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "color": cat.color}


@router.get("")
def list_assets(
    status: str = Query(None),
    category_id: str = Query(None),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(Asset).filter(Asset.org_id == org_id)
    if status:
        q = q.filter(Asset.status == status)
    if category_id:
        q = q.filter(Asset.category_id == category_id)
    if search:
        q = q.filter(
            (Asset.name.ilike(f"%{search}%")) |
            (Asset.asset_tag.ilike(f"%{search}%")) |
            (Asset.serial_number.ilike(f"%{search}%"))
        )
    assets = q.order_by(desc(Asset.updated_at)).all()
    return [_serialize_asset(a) for a in assets]


@router.post("")
def create_asset(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = Asset(
        org_id=org_id,
        category_id=data.get("category_id"),
        name=data["name"],
        asset_tag=data.get("asset_tag"),
        serial_number=data.get("serial_number"),
        make=data.get("make"),
        model=data.get("model"),
        description=data.get("description"),
        status=data.get("status", "available"),
        condition=data.get("condition", "good"),
        purchase_date=datetime.fromisoformat(data["purchase_date"]) if data.get("purchase_date") else None,
        purchase_cost=float(data.get("purchase_cost", 0)),
        current_value=float(data.get("current_value") or data.get("purchase_cost", 0)),
        depreciation_method=data.get("depreciation_method", "straight_line"),
        depreciation_rate=float(data.get("depreciation_rate", 0)),
        useful_life_years=float(data.get("useful_life_years", 5)),
        salvage_value=float(data.get("salvage_value", 0)),
        warranty_expiry=datetime.fromisoformat(data["warranty_expiry"]) if data.get("warranty_expiry") else None,
        location_description=data.get("location_description"),
        assigned_to_user_id=data.get("assigned_to_user_id"),
        assigned_to_crew_id=data.get("assigned_to_crew_id"),
        assigned_to_project_id=data.get("assigned_to_project_id"),
        notes=data.get("notes"),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _serialize_asset(asset)


@router.get("/stats")
def get_asset_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    total = db.query(func.count(Asset.id)).filter(Asset.org_id == org_id).scalar() or 0
    total_value = float(db.query(func.coalesce(func.sum(Asset.current_value), 0)).filter(Asset.org_id == org_id).scalar() or 0)
    total_purchase = float(db.query(func.coalesce(func.sum(Asset.purchase_cost), 0)).filter(Asset.org_id == org_id).scalar() or 0)

    by_status = {}
    status_rows = db.query(Asset.status, func.count(Asset.id)).filter(Asset.org_id == org_id).group_by(Asset.status).all()
    for s, c in status_rows:
        by_status[s.value if hasattr(s, 'value') else str(s)] = c

    by_category = {}
    cat_rows = db.query(AssetCategory.name, func.count(Asset.id)).join(Asset, Asset.category_id == AssetCategory.id).filter(Asset.org_id == org_id).group_by(AssetCategory.name).all()
    for n, c in cat_rows:
        by_category[n] = c

    open_incidents = db.query(func.count(AssetIncident.id)).join(Asset).filter(
        Asset.org_id == org_id, AssetIncident.status == "open").scalar() or 0
    pending_maintenance = db.query(func.count(AssetMaintenance.id)).join(Asset).filter(
        Asset.org_id == org_id, AssetMaintenance.status == "scheduled").scalar() or 0
    vehicle_count = db.query(func.count(FleetVehicle.id)).filter(FleetVehicle.org_id == org_id).scalar() or 0
    depreciation_total = total_purchase - total_value

    return {
        "total_assets": total,
        "total_value": total_value,
        "total_purchase_cost": total_purchase,
        "depreciation_total": depreciation_total,
        "by_status": by_status,
        "by_category": by_category,
        "open_incidents": open_incidents,
        "pending_maintenance": pending_maintenance,
        "vehicle_count": vehicle_count,
    }


@router.get("/ai/insights")
def get_asset_ai_insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    from app.services import ai_service

    assets = db.query(Asset).filter(Asset.org_id == org_id).all()
    total_value = sum(float(a.current_value or 0) for a in assets)
    total_purchase = sum(float(a.purchase_cost or 0) for a in assets)

    by_status = {}
    for a in assets:
        s = a.status.value if a.status else "available"
        by_status[s] = by_status.get(s, 0) + 1

    incidents = db.query(AssetIncident).join(Asset).filter(Asset.org_id == org_id).order_by(desc(AssetIncident.occurred_at)).limit(20).all()
    incident_data = [{"type": i.incident_type, "severity": i.severity, "cost": float(i.damage_cost or 0), "status": i.status} for i in incidents]

    maint = db.query(AssetMaintenance).join(Asset).filter(Asset.org_id == org_id, AssetMaintenance.status == "scheduled").all()
    maint_data = [{"type": m.maintenance_type, "cost": float(m.cost or 0), "asset": m.asset.name if m.asset else ""} for m in maint[:10]]

    asset_summary = {
        "total_assets": len(assets),
        "total_current_value": total_value,
        "total_purchase_cost": total_purchase,
        "depreciation": total_purchase - total_value,
        "by_status": by_status,
        "recent_incidents": incident_data[:10],
        "pending_maintenance": maint_data,
    }

    insights = ai_service.generate_asset_insights(asset_summary)
    return {"insights": insights}


@router.get("/{asset_id}")
def get_asset(asset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _serialize_asset(asset)


@router.put("/{asset_id}")
def update_asset(asset_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    fields = ["name", "asset_tag", "serial_number", "make", "model", "description",
              "status", "condition", "depreciation_method", "location_description",
              "assigned_to_user_id", "assigned_to_crew_id", "assigned_to_project_id",
              "notes", "category_id", "image_url"]
    for f in fields:
        if f in data:
            setattr(asset, f, data[f])

    float_fields = ["purchase_cost", "current_value", "depreciation_rate", "useful_life_years", "salvage_value"]
    for f in float_fields:
        if f in data:
            setattr(asset, f, float(data[f]) if data[f] is not None else 0)

    date_fields = ["purchase_date", "warranty_expiry"]
    for f in date_fields:
        if f in data:
            setattr(asset, f, datetime.fromisoformat(data[f]) if data[f] else None)

    db.commit()
    db.refresh(asset)
    return _serialize_asset(asset)


@router.delete("/{asset_id}")
def delete_asset(asset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(asset)
    db.commit()
    return {"ok": True}


@router.get("/{asset_id}/allocations")
def list_allocations(asset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    allocs = db.query(AssetAllocation).filter(AssetAllocation.asset_id == asset_id).order_by(desc(AssetAllocation.start_at)).all()
    return [{
        "id": a.id,
        "asset_id": a.asset_id,
        "assigned_to_user_id": a.assigned_to_user_id,
        "user_name": a.user.full_name if a.user else None,
        "assigned_to_crew_id": a.assigned_to_crew_id,
        "crew_name": a.crew.name if a.crew else None,
        "project_id": a.project_id,
        "project_name": a.project.name if a.project else None,
        "start_at": str(a.start_at),
        "end_at": str(a.end_at) if a.end_at else None,
        "reason": a.reason,
        "allocated_by": a.allocated_by,
        "allocator_name": a.allocator.full_name if a.allocator else None,
        "returned_condition": a.returned_condition,
        "notes": a.notes,
    } for a in allocs]


@router.post("/{asset_id}/allocations")
def create_allocation(asset_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    alloc = AssetAllocation(
        asset_id=asset_id,
        assigned_to_user_id=data.get("assigned_to_user_id"),
        assigned_to_crew_id=data.get("assigned_to_crew_id"),
        project_id=data.get("project_id"),
        start_at=datetime.fromisoformat(data["start_at"]) if data.get("start_at") else datetime.utcnow(),
        end_at=datetime.fromisoformat(data["end_at"]) if data.get("end_at") else None,
        reason=data.get("reason"),
        allocated_by=user.id,
        notes=data.get("notes"),
    )
    db.add(alloc)

    asset.status = "assigned"
    if data.get("assigned_to_user_id"):
        asset.assigned_to_user_id = data["assigned_to_user_id"]
    if data.get("assigned_to_crew_id"):
        asset.assigned_to_crew_id = data["assigned_to_crew_id"]
    if data.get("project_id"):
        asset.assigned_to_project_id = data["project_id"]

    db.commit()
    return {"ok": True, "allocation_id": alloc.id}


@router.put("/{asset_id}/allocations/{alloc_id}/return")
def return_allocation(asset_id: str, alloc_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    alloc = db.query(AssetAllocation).filter(AssetAllocation.id == alloc_id, AssetAllocation.asset_id == asset_id).first()
    if not alloc:
        raise HTTPException(status_code=404, detail="Allocation not found")
    alloc.end_at = datetime.utcnow()
    alloc.returned_condition = data.get("returned_condition", "good")
    alloc.notes = data.get("notes", alloc.notes)
    asset.status = "available"
    asset.assigned_to_user_id = None
    asset.assigned_to_crew_id = None
    asset.assigned_to_project_id = None
    db.commit()
    return {"ok": True}


@router.get("/{asset_id}/incidents")
def list_incidents(asset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    incidents = db.query(AssetIncident).filter(AssetIncident.asset_id == asset_id).order_by(desc(AssetIncident.occurred_at)).all()
    return [{
        "id": i.id,
        "asset_id": i.asset_id,
        "reported_by": i.reported_by,
        "reporter_name": i.reporter.full_name if i.reporter else None,
        "incident_type": i.incident_type,
        "severity": i.severity,
        "title": i.title,
        "description": i.description,
        "occurred_at": str(i.occurred_at),
        "location_description": i.location_description,
        "damage_cost": float(i.damage_cost or 0),
        "resolution": i.resolution,
        "resolved_at": str(i.resolved_at) if i.resolved_at else None,
        "status": i.status,
    } for i in incidents]


@router.post("/{asset_id}/incidents")
def create_incident(asset_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    incident = AssetIncident(
        asset_id=asset_id,
        reported_by=user.id,
        incident_type=data.get("incident_type", "damage"),
        severity=data.get("severity", "medium"),
        title=data["title"],
        description=data.get("description"),
        occurred_at=datetime.fromisoformat(data["occurred_at"]) if data.get("occurred_at") else datetime.utcnow(),
        location_description=data.get("location_description"),
        location_lat=data.get("location_lat"),
        location_lng=data.get("location_lng"),
        damage_cost=float(data.get("damage_cost", 0)),
    )
    db.add(incident)
    if data.get("update_asset_status"):
        asset.status = "damaged"
    db.commit()
    return {"ok": True, "incident_id": incident.id}


@router.put("/{asset_id}/incidents/{incident_id}/resolve")
def resolve_incident(asset_id: str, incident_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    incident = db.query(AssetIncident).join(Asset).filter(
        AssetIncident.id == incident_id, Asset.org_id == org_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.resolution = data.get("resolution")
    incident.resolved_at = datetime.utcnow()
    incident.status = "resolved"
    db.commit()
    return {"ok": True}


@router.get("/{asset_id}/maintenance")
def list_maintenance(asset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    records = db.query(AssetMaintenance).filter(AssetMaintenance.asset_id == asset_id).order_by(desc(AssetMaintenance.scheduled_at)).all()
    return [{
        "id": r.id,
        "asset_id": r.asset_id,
        "maintenance_type": r.maintenance_type,
        "title": r.title,
        "description": r.description,
        "scheduled_at": str(r.scheduled_at) if r.scheduled_at else None,
        "completed_at": str(r.completed_at) if r.completed_at else None,
        "vendor": r.vendor,
        "cost": float(r.cost or 0),
        "status": r.status,
        "performed_by": r.performed_by,
        "performer_name": r.performer.full_name if r.performer else None,
        "notes": r.notes,
        "next_due_at": str(r.next_due_at) if r.next_due_at else None,
    } for r in records]


@router.post("/{asset_id}/maintenance")
def create_maintenance(asset_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.org_id == org_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    record = AssetMaintenance(
        asset_id=asset_id,
        maintenance_type=data.get("maintenance_type", "preventive"),
        title=data["title"],
        description=data.get("description"),
        scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
        vendor=data.get("vendor"),
        cost=float(data.get("cost", 0)),
        performed_by=data.get("performed_by"),
        notes=data.get("notes"),
        next_due_at=datetime.fromisoformat(data["next_due_at"]) if data.get("next_due_at") else None,
    )
    db.add(record)
    db.commit()
    return {"ok": True, "maintenance_id": record.id}


@router.put("/{asset_id}/maintenance/{maint_id}/complete")
def complete_maintenance(asset_id: str, maint_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    record = db.query(AssetMaintenance).join(Asset).filter(
        AssetMaintenance.id == maint_id, Asset.org_id == org_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    record.completed_at = datetime.utcnow()
    record.status = "completed"
    record.cost = float(data.get("cost", record.cost))
    record.notes = data.get("notes", record.notes)
    db.commit()
    return {"ok": True}
