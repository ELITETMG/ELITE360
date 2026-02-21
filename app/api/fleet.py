import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    FleetVehicle, FleetVehicleStatus, FleetTelemetry,
    TechnicianLocation, TelematicsIntegration,
    User, OrgMember, Crew, Asset
)

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


def _get_user_org(db: Session, user: User):
    mem = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not mem:
        raise HTTPException(status_code=403, detail="No org membership")
    return mem.org_id


def _serialize_vehicle(v):
    return {
        "id": v.id,
        "org_id": v.org_id,
        "asset_id": v.asset_id,
        "name": v.name,
        "vin": v.vin,
        "make": v.make,
        "model": v.model,
        "year": v.year,
        "license_plate": v.license_plate,
        "color": v.color,
        "vehicle_type": v.vehicle_type,
        "status": v.status.value if v.status else "active",
        "assigned_driver_id": v.assigned_driver_id,
        "driver_name": v.driver.full_name if v.driver else None,
        "assigned_crew_id": v.assigned_crew_id,
        "crew_name": v.crew.name if v.crew else None,
        "current_lat": v.current_lat,
        "current_lng": v.current_lng,
        "current_speed": float(v.current_speed or 0),
        "current_heading": float(v.current_heading or 0),
        "odometer": float(v.odometer or 0),
        "fuel_level": float(v.fuel_level) if v.fuel_level is not None else None,
        "engine_hours": float(v.engine_hours or 0),
        "last_location_update": str(v.last_location_update) if v.last_location_update else None,
        "telematics_provider": v.telematics_provider,
        "telematics_vehicle_id": v.telematics_vehicle_id,
        "insurance_expiry": str(v.insurance_expiry) if v.insurance_expiry else None,
        "registration_expiry": str(v.registration_expiry) if v.registration_expiry else None,
        "notes": v.notes,
        "created_at": str(v.created_at),
    }


@router.get("/vehicles")
def list_vehicles(
    status: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(FleetVehicle).filter(FleetVehicle.org_id == org_id)
    if status:
        q = q.filter(FleetVehicle.status == status)
    vehicles = q.order_by(FleetVehicle.name).all()
    return [_serialize_vehicle(v) for v in vehicles]


@router.post("/vehicles")
def create_vehicle(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    vehicle = FleetVehicle(
        org_id=org_id,
        name=data["name"],
        vin=data.get("vin"),
        make=data.get("make"),
        model=data.get("model"),
        year=int(data["year"]) if data.get("year") else None,
        license_plate=data.get("license_plate"),
        color=data.get("color"),
        vehicle_type=data.get("vehicle_type", "truck"),
        status=data.get("status", "active"),
        assigned_driver_id=data.get("assigned_driver_id"),
        assigned_crew_id=data.get("assigned_crew_id"),
        odometer=float(data.get("odometer", 0)),
        fuel_level=float(data["fuel_level"]) if data.get("fuel_level") is not None else None,
        engine_hours=float(data.get("engine_hours", 0)),
        telematics_provider=data.get("telematics_provider"),
        telematics_vehicle_id=data.get("telematics_vehicle_id"),
        insurance_expiry=datetime.fromisoformat(data["insurance_expiry"]) if data.get("insurance_expiry") else None,
        registration_expiry=datetime.fromisoformat(data["registration_expiry"]) if data.get("registration_expiry") else None,
        notes=data.get("notes"),
        asset_id=data.get("asset_id"),
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return _serialize_vehicle(vehicle)


@router.get("/vehicles/stats")
def get_fleet_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    total = db.query(func.count(FleetVehicle.id)).filter(FleetVehicle.org_id == org_id).scalar() or 0
    active = db.query(func.count(FleetVehicle.id)).filter(
        FleetVehicle.org_id == org_id, FleetVehicle.status == FleetVehicleStatus.ACTIVE).scalar() or 0
    in_shop = db.query(func.count(FleetVehicle.id)).filter(
        FleetVehicle.org_id == org_id, FleetVehicle.status == FleetVehicleStatus.IN_SHOP).scalar() or 0

    total_odometer = float(db.query(func.coalesce(func.sum(FleetVehicle.odometer), 0)).filter(
        FleetVehicle.org_id == org_id).scalar() or 0)
    avg_fuel = db.query(func.avg(FleetVehicle.fuel_level)).filter(
        FleetVehicle.org_id == org_id, FleetVehicle.fuel_level.isnot(None)).scalar()

    with_location = db.query(func.count(FleetVehicle.id)).filter(
        FleetVehicle.org_id == org_id,
        FleetVehicle.current_lat.isnot(None),
        FleetVehicle.current_lng.isnot(None)
    ).scalar() or 0

    active_techs = db.query(func.count(TechnicianLocation.id)).filter(
        TechnicianLocation.org_id == org_id, TechnicianLocation.is_active == True).scalar() or 0

    integrations = db.query(TelematicsIntegration).filter(
        TelematicsIntegration.org_id == org_id, TelematicsIntegration.is_active == True).count()

    return {
        "total_vehicles": total,
        "active_vehicles": active,
        "in_shop": in_shop,
        "total_odometer": total_odometer,
        "avg_fuel_level": round(float(avg_fuel or 0), 1),
        "vehicles_with_location": with_location,
        "active_technicians": active_techs,
        "active_integrations": integrations,
    }


@router.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    v = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id, FleetVehicle.org_id == org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _serialize_vehicle(v)


@router.put("/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    v = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id, FleetVehicle.org_id == org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    fields = ["name", "vin", "make", "model", "license_plate", "color", "vehicle_type",
              "status", "assigned_driver_id", "assigned_crew_id", "telematics_provider",
              "telematics_vehicle_id", "notes", "asset_id"]
    for f in fields:
        if f in data:
            setattr(v, f, data[f])
    if "year" in data:
        v.year = int(data["year"]) if data["year"] else None
    float_fields = ["odometer", "fuel_level", "engine_hours"]
    for f in float_fields:
        if f in data:
            setattr(v, f, float(data[f]) if data[f] is not None else None)
    date_fields = ["insurance_expiry", "registration_expiry"]
    for f in date_fields:
        if f in data:
            setattr(v, f, datetime.fromisoformat(data[f]) if data[f] else None)

    db.commit()
    db.refresh(v)
    return _serialize_vehicle(v)


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    v = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id, FleetVehicle.org_id == org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.put("/vehicles/{vehicle_id}/location")
def update_vehicle_location(vehicle_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    v = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id, FleetVehicle.org_id == org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    v.current_lat = float(data["lat"])
    v.current_lng = float(data["lng"])
    v.current_speed = float(data.get("speed", 0))
    v.current_heading = float(data.get("heading", 0))
    v.last_location_update = datetime.utcnow()
    if data.get("odometer"):
        v.odometer = float(data["odometer"])
    if data.get("fuel_level") is not None:
        v.fuel_level = float(data["fuel_level"])

    telemetry = FleetTelemetry(
        vehicle_id=vehicle_id,
        provider=data.get("provider", "manual"),
        lat=v.current_lat,
        lng=v.current_lng,
        speed=v.current_speed,
        heading=v.current_heading,
        odometer=v.odometer,
        fuel_level=v.fuel_level,
        engine_status=data.get("engine_status"),
        event_type=data.get("event_type", "location_update"),
    )
    db.add(telemetry)
    db.commit()
    return {"ok": True}


@router.get("/vehicles/{vehicle_id}/telemetry")
def get_vehicle_telemetry(
    vehicle_id: str,
    limit: int = Query(50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    v = db.query(FleetVehicle).filter(FleetVehicle.id == vehicle_id, FleetVehicle.org_id == org_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    records = db.query(FleetTelemetry).filter(FleetTelemetry.vehicle_id == vehicle_id).order_by(desc(FleetTelemetry.event_time)).limit(limit).all()
    return [{
        "id": r.id,
        "lat": r.lat,
        "lng": r.lng,
        "speed": float(r.speed or 0),
        "heading": float(r.heading or 0),
        "odometer": float(r.odometer or 0) if r.odometer else None,
        "fuel_level": float(r.fuel_level) if r.fuel_level is not None else None,
        "engine_status": r.engine_status,
        "event_type": r.event_type,
        "event_time": str(r.event_time),
        "provider": r.provider,
    } for r in records]


@router.post("/tech/checkin")
def tech_checkin(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    existing = db.query(TechnicianLocation).filter(
        TechnicianLocation.user_id == user.id, TechnicianLocation.is_active == True).first()
    if existing:
        existing.is_active = False

    loc = TechnicianLocation(
        user_id=user.id,
        org_id=org_id,
        lat=float(data["lat"]),
        lng=float(data["lng"]),
        accuracy=float(data.get("accuracy", 0)) if data.get("accuracy") else None,
        altitude=float(data.get("altitude")) if data.get("altitude") else None,
        speed=float(data.get("speed")) if data.get("speed") else None,
        heading=float(data.get("heading")) if data.get("heading") else None,
        source=data.get("source", "mobile_checkin"),
        device_info=data.get("device_info"),
        battery_level=float(data.get("battery_level")) if data.get("battery_level") else None,
        is_active=True,
    )
    db.add(loc)
    db.commit()
    return {"ok": True, "location_id": loc.id}


@router.post("/tech/checkout")
def tech_checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    active = db.query(TechnicianLocation).filter(
        TechnicianLocation.user_id == user.id, TechnicianLocation.is_active == True).all()
    for loc in active:
        loc.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/tech/locations")
def get_tech_locations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    locs = db.query(TechnicianLocation).filter(
        TechnicianLocation.org_id == org_id, TechnicianLocation.is_active == True
    ).order_by(desc(TechnicianLocation.event_time)).all()
    return [{
        "id": l.id,
        "user_id": l.user_id,
        "user_name": l.user.full_name if l.user else None,
        "lat": l.lat,
        "lng": l.lng,
        "accuracy": l.accuracy,
        "speed": l.speed,
        "heading": l.heading,
        "source": l.source,
        "battery_level": l.battery_level,
        "event_time": str(l.event_time),
        "is_active": l.is_active,
    } for l in locs]


@router.get("/tech/locations/history")
def get_tech_location_history(
    user_id: str = Query(None),
    hours: int = Query(24),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    since = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(TechnicianLocation).filter(
        TechnicianLocation.org_id == org_id,
        TechnicianLocation.event_time >= since
    )
    if user_id:
        q = q.filter(TechnicianLocation.user_id == user_id)
    locs = q.order_by(TechnicianLocation.event_time).all()
    return [{
        "user_id": l.user_id,
        "user_name": l.user.full_name if l.user else None,
        "lat": l.lat,
        "lng": l.lng,
        "event_time": str(l.event_time),
        "source": l.source,
    } for l in locs]


@router.get("/integrations")
def list_integrations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    integs = db.query(TelematicsIntegration).filter(TelematicsIntegration.org_id == org_id).all()
    return [{
        "id": i.id,
        "provider": i.provider,
        "display_name": i.display_name,
        "api_endpoint": i.api_endpoint,
        "account_id": i.account_id,
        "is_active": i.is_active,
        "last_sync_at": str(i.last_sync_at) if i.last_sync_at else None,
        "sync_interval_minutes": i.sync_interval_minutes,
        "vehicle_count": i.vehicle_count,
        "status": i.status,
        "error_message": i.error_message,
        "created_at": str(i.created_at),
    } for i in integs]


@router.post("/integrations")
def create_integration(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    existing = db.query(TelematicsIntegration).filter(
        TelematicsIntegration.org_id == org_id, TelematicsIntegration.provider == data["provider"]).first()
    if existing:
        existing.display_name = data.get("display_name", existing.display_name)
        existing.api_endpoint = data.get("api_endpoint", existing.api_endpoint)
        existing.api_key_ref = data.get("api_key_ref")
        existing.database_name = data.get("database_name")
        existing.account_id = data.get("account_id")
        existing.is_active = data.get("is_active", True)
        existing.sync_interval_minutes = int(data.get("sync_interval_minutes", 5))
        existing.config_json = json.dumps(data.get("config", {})) if data.get("config") else existing.config_json
        existing.status = "configured"
        existing.error_message = None
        db.commit()
        return {"ok": True, "integration_id": existing.id, "updated": True}

    integ = TelematicsIntegration(
        org_id=org_id,
        provider=data["provider"],
        display_name=data.get("display_name", data["provider"].title()),
        api_endpoint=data.get("api_endpoint"),
        api_key_ref=data.get("api_key_ref"),
        database_name=data.get("database_name"),
        account_id=data.get("account_id"),
        is_active=data.get("is_active", True),
        sync_interval_minutes=int(data.get("sync_interval_minutes", 5)),
        config_json=json.dumps(data.get("config", {})) if data.get("config") else None,
        status="configured",
    )
    db.add(integ)
    db.commit()
    return {"ok": True, "integration_id": integ.id}


@router.delete("/integrations/{integ_id}")
def delete_integration(integ_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    integ = db.query(TelematicsIntegration).filter(
        TelematicsIntegration.id == integ_id, TelematicsIntegration.org_id == org_id).first()
    if not integ:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integ)
    db.commit()
    return {"ok": True}


@router.post("/integrations/{integ_id}/sync")
def sync_integration(integ_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    integ = db.query(TelematicsIntegration).filter(
        TelematicsIntegration.id == integ_id, TelematicsIntegration.org_id == org_id).first()
    if not integ:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        if integ.provider == "samsara":
            result = _sync_samsara(db, integ, org_id)
        elif integ.provider == "geotab":
            result = _sync_geotab(db, integ, org_id)
        elif integ.provider == "verizon_connect":
            result = _sync_verizon(db, integ, org_id)
        else:
            result = {"synced": 0, "message": f"Unknown provider: {integ.provider}"}

        integ.last_sync_at = datetime.utcnow()
        integ.status = "synced"
        integ.vehicle_count = result.get("synced", 0)
        integ.error_message = None
        db.commit()
        return {"ok": True, "result": result}
    except Exception as e:
        integ.status = "error"
        integ.error_message = str(e)[:500]
        db.commit()
        return {"ok": False, "error": str(e)}


def _sync_samsara(db: Session, integ: TelematicsIntegration, org_id: str) -> dict:
    import httpx
    api_key = integ.api_key_ref
    if not api_key:
        return {"synced": 0, "message": "No API key configured"}

    try:
        endpoint = integ.api_endpoint or "https://api.samsara.com"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{endpoint}/fleet/vehicles/locations", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                vehicles = data.get("data", [])
                synced = 0
                for v_data in vehicles:
                    loc = v_data.get("location", {})
                    v_id = str(v_data.get("id", ""))
                    vehicle = db.query(FleetVehicle).filter(
                        FleetVehicle.org_id == org_id,
                        FleetVehicle.telematics_vehicle_id == v_id
                    ).first()
                    if not vehicle:
                        vehicle = FleetVehicle(
                            org_id=org_id,
                            name=v_data.get("name", f"Samsara-{v_id}"),
                            telematics_provider="samsara",
                            telematics_vehicle_id=v_id,
                        )
                        db.add(vehicle)
                        db.flush()

                    if loc.get("latitude") and loc.get("longitude"):
                        vehicle.current_lat = float(loc["latitude"])
                        vehicle.current_lng = float(loc["longitude"])
                        vehicle.current_speed = float(loc.get("speed", 0)) * 0.621371
                        vehicle.current_heading = float(loc.get("heading", 0))
                        vehicle.last_location_update = datetime.utcnow()

                        telemetry = FleetTelemetry(
                            vehicle_id=vehicle.id, provider="samsara",
                            lat=vehicle.current_lat, lng=vehicle.current_lng,
                            speed=vehicle.current_speed, heading=vehicle.current_heading,
                            event_type="samsara_sync",
                        )
                        db.add(telemetry)
                    synced += 1
                db.commit()
                return {"synced": synced, "message": f"Synced {synced} vehicles from Samsara"}
            else:
                return {"synced": 0, "message": f"Samsara API error: {resp.status_code}"}
    except Exception as e:
        return {"synced": 0, "message": f"Samsara sync error: {str(e)}"}


def _sync_geotab(db: Session, integ: TelematicsIntegration, org_id: str) -> dict:
    import httpx
    api_key = integ.api_key_ref
    database = integ.database_name
    if not api_key or not database:
        return {"synced": 0, "message": "GeoTab requires API key and database name"}

    try:
        endpoint = integ.api_endpoint or "https://my.geotab.com/apiv1"
        config = json.loads(integ.config_json) if integ.config_json else {}
        username = config.get("username", "")

        auth_payload = {
            "method": "Authenticate",
            "params": {"database": database, "userName": username, "password": api_key}
        }

        with httpx.Client(timeout=30) as client:
            auth_resp = client.post(endpoint, json=auth_payload)
            if auth_resp.status_code != 200:
                return {"synced": 0, "message": f"GeoTab auth failed: {auth_resp.status_code}"}

            auth_data = auth_resp.json()
            credentials = auth_data.get("result", {}).get("credentials", {})
            session_id = credentials.get("sessionId", "")

            device_payload = {
                "method": "Get",
                "params": {
                    "typeName": "DeviceStatusInfo",
                    "credentials": credentials
                }
            }
            dev_resp = client.post(endpoint, json=device_payload)
            if dev_resp.status_code == 200:
                devices = dev_resp.json().get("result", [])
                synced = 0
                for dev in devices:
                    dev_id = str(dev.get("device", {}).get("id", ""))
                    vehicle = db.query(FleetVehicle).filter(
                        FleetVehicle.org_id == org_id,
                        FleetVehicle.telematics_vehicle_id == dev_id
                    ).first()
                    if not vehicle:
                        vehicle = FleetVehicle(
                            org_id=org_id,
                            name=f"GeoTab-{dev_id}",
                            telematics_provider="geotab",
                            telematics_vehicle_id=dev_id,
                        )
                        db.add(vehicle)
                        db.flush()

                    lat = dev.get("latitude")
                    lng = dev.get("longitude")
                    if lat and lng:
                        vehicle.current_lat = float(lat)
                        vehicle.current_lng = float(lng)
                        vehicle.current_speed = float(dev.get("speed", 0))
                        vehicle.last_location_update = datetime.utcnow()

                        telemetry = FleetTelemetry(
                            vehicle_id=vehicle.id, provider="geotab",
                            lat=vehicle.current_lat, lng=vehicle.current_lng,
                            speed=vehicle.current_speed,
                            event_type="geotab_sync",
                        )
                        db.add(telemetry)
                    synced += 1
                db.commit()
                return {"synced": synced, "message": f"Synced {synced} devices from GeoTab"}
            return {"synced": 0, "message": "Failed to fetch GeoTab devices"}
    except Exception as e:
        return {"synced": 0, "message": f"GeoTab sync error: {str(e)}"}


def _sync_verizon(db: Session, integ: TelematicsIntegration, org_id: str) -> dict:
    import httpx
    api_key = integ.api_key_ref
    account_id = integ.account_id
    if not api_key:
        return {"synced": 0, "message": "Verizon Connect requires API key"}

    try:
        endpoint = integ.api_endpoint or "https://fim.api.us.fleetmatics.com/rad/v1"
        headers = {
            "Authorization": f"Atmosphere atmosphere_app_id={account_id or ''}, Bearer {api_key}",
            "Content-Type": "application/json"
        }

        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{endpoint}/vehicles", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                vehicles_data = data if isinstance(data, list) else data.get("vehicles", data.get("data", []))
                synced = 0
                for v_data in vehicles_data:
                    v_id = str(v_data.get("vehicleId", v_data.get("id", "")))
                    vehicle = db.query(FleetVehicle).filter(
                        FleetVehicle.org_id == org_id,
                        FleetVehicle.telematics_vehicle_id == v_id
                    ).first()
                    if not vehicle:
                        vehicle = FleetVehicle(
                            org_id=org_id,
                            name=v_data.get("vehicleName", v_data.get("name", f"VC-{v_id}")),
                            telematics_provider="verizon_connect",
                            telematics_vehicle_id=v_id,
                        )
                        db.add(vehicle)
                        db.flush()

                    lat = v_data.get("latitude", v_data.get("lat"))
                    lng = v_data.get("longitude", v_data.get("lng"))
                    if lat and lng:
                        vehicle.current_lat = float(lat)
                        vehicle.current_lng = float(lng)
                        vehicle.current_speed = float(v_data.get("speed", 0))
                        vehicle.last_location_update = datetime.utcnow()

                        telemetry = FleetTelemetry(
                            vehicle_id=vehicle.id, provider="verizon_connect",
                            lat=vehicle.current_lat, lng=vehicle.current_lng,
                            speed=vehicle.current_speed,
                            event_type="verizon_sync",
                        )
                        db.add(telemetry)
                    synced += 1
                db.commit()
                return {"synced": synced, "message": f"Synced {synced} vehicles from Verizon Connect"}
            else:
                return {"synced": 0, "message": f"Verizon API error: {resp.status_code}"}
    except Exception as e:
        return {"synced": 0, "message": f"Verizon sync error: {str(e)}"}


@router.get("/ai/insights")
def get_fleet_ai_insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    from app.services import ai_service

    vehicles = db.query(FleetVehicle).filter(FleetVehicle.org_id == org_id).all()
    vehicle_data = [{
        "name": v.name, "type": v.vehicle_type, "status": v.status.value if v.status else "active",
        "odometer": float(v.odometer or 0), "fuel_level": float(v.fuel_level) if v.fuel_level is not None else None,
        "engine_hours": float(v.engine_hours or 0), "make": v.make, "model": v.model, "year": v.year,
        "has_location": v.current_lat is not None,
    } for v in vehicles]

    active_techs = db.query(TechnicianLocation).filter(
        TechnicianLocation.org_id == org_id, TechnicianLocation.is_active == True).count()

    fleet_summary = {
        "total_vehicles": len(vehicles),
        "vehicles": vehicle_data[:15],
        "active_technicians": active_techs,
    }

    insights = ai_service.generate_fleet_insights(fleet_summary)
    return {"insights": insights}


@router.get("/map/all")
def get_all_map_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    vehicles = db.query(FleetVehicle).filter(
        FleetVehicle.org_id == org_id,
        FleetVehicle.current_lat.isnot(None),
        FleetVehicle.current_lng.isnot(None)
    ).all()

    techs = db.query(TechnicianLocation).filter(
        TechnicianLocation.org_id == org_id,
        TechnicianLocation.is_active == True
    ).all()

    return {
        "vehicles": [{
            "id": v.id, "name": v.name, "type": v.vehicle_type,
            "lat": v.current_lat, "lng": v.current_lng,
            "speed": float(v.current_speed or 0),
            "heading": float(v.current_heading or 0),
            "status": v.status.value if v.status else "active",
            "driver": v.driver.full_name if v.driver else None,
            "last_update": str(v.last_location_update) if v.last_location_update else None,
        } for v in vehicles],
        "technicians": [{
            "id": t.id, "user_id": t.user_id,
            "name": t.user.full_name if t.user else None,
            "lat": t.lat, "lng": t.lng,
            "speed": t.speed, "battery": t.battery_level,
            "source": t.source,
            "event_time": str(t.event_time),
        } for t in techs],
    }