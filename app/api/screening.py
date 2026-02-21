import math
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.models import (
    ScreeningRequest, ScreeningProvider, ScreeningStatus,
    DrugScreenFacility, DrugScreenAppointment,
    OrgMember, User
)

router = APIRouter(prefix="/api/screening", tags=["screening"])


def _get_user_org(db: Session, user: User):
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No org membership")
    return membership.org_id


def _haversine(lat1, lon1, lat2, lon2):
    R = 3959
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


ZIP_COORDS = {
    "78701": (30.2672, -97.7431), "78702": (30.2630, -97.7200), "78703": (30.2900, -97.7700),
    "78704": (30.2400, -97.7600), "78705": (30.2950, -97.7400), "78745": (30.2100, -97.7900),
    "78748": (30.1800, -97.7900), "78758": (30.3700, -97.7100), "78759": (30.3900, -97.7600),
    "73301": (30.2672, -97.7431), "75201": (32.7876, -96.7985), "75202": (32.7767, -96.7970),
    "77001": (29.7604, -95.3698), "77002": (29.7530, -95.3570), "77003": (29.7450, -95.3400),
    "85001": (33.4484, -112.0740), "85004": (33.4500, -112.0700), "90001": (33.9400, -118.2500),
    "10001": (40.7484, -73.9967), "60601": (41.8781, -87.6298), "30301": (33.7570, -84.3901),
}

SAMPLE_FACILITIES = [
    {"name": "Concentra Urgent Care - Downtown", "facility_type": "concentra", "address": "100 Congress Ave, Suite 100", "city": "Austin", "state": "TX", "zip_code": "78701", "phone": "(512) 555-0101", "latitude": 30.2672, "longitude": -97.7431, "hours": "Mon-Fri 8AM-5PM, Sat 9AM-1PM", "accepts_walk_ins": True, "services": "DOT physicals, drug testing, pre-employment screening, workers comp", "network": "Concentra", "is_verified": True},
    {"name": "Concentra Urgent Care - North Austin", "facility_type": "concentra", "address": "8868 Research Blvd, Suite 200", "city": "Austin", "state": "TX", "zip_code": "78758", "phone": "(512) 555-0102", "latitude": 30.3710, "longitude": -97.7065, "hours": "Mon-Fri 8AM-5PM", "accepts_walk_ins": True, "services": "DOT physicals, drug testing, pre-employment screening", "network": "Concentra", "is_verified": True},
    {"name": "Concentra Urgent Care - South Austin", "facility_type": "concentra", "address": "4302 S Lamar Blvd", "city": "Austin", "state": "TX", "zip_code": "78745", "phone": "(512) 555-0103", "latitude": 30.2280, "longitude": -97.7880, "hours": "Mon-Fri 8AM-5PM, Sat 9AM-12PM", "accepts_walk_ins": True, "services": "DOT physicals, drug testing, pre-employment screening, workers comp", "network": "Concentra", "is_verified": True},
    {"name": "FastMed Urgent Care - East Austin", "facility_type": "urgent_care", "address": "2120 E Riverside Dr", "city": "Austin", "state": "TX", "zip_code": "78702", "phone": "(512) 555-0104", "latitude": 30.2350, "longitude": -97.7250, "hours": "Mon-Sun 8AM-8PM", "accepts_walk_ins": True, "services": "Drug testing, pre-employment physicals, rapid testing", "network": "FastMed", "is_verified": True},
    {"name": "NextCare Urgent Care - Cedar Park", "facility_type": "urgent_care", "address": "1401 Medical Pkwy", "city": "Cedar Park", "state": "TX", "zip_code": "78613", "phone": "(512) 555-0105", "latitude": 30.5100, "longitude": -97.8200, "hours": "Mon-Fri 8AM-8PM, Sat-Sun 8AM-4PM", "accepts_walk_ins": True, "services": "Drug testing, DOT physicals, occupational health", "network": "NextCare", "is_verified": True},
    {"name": "Concentra Urgent Care - Dallas Downtown", "facility_type": "concentra", "address": "1717 Main St", "city": "Dallas", "state": "TX", "zip_code": "75201", "phone": "(214) 555-0201", "latitude": 32.7830, "longitude": -96.7990, "hours": "Mon-Fri 8AM-5PM", "accepts_walk_ins": True, "services": "DOT physicals, drug testing, pre-employment screening", "network": "Concentra", "is_verified": True},
    {"name": "Concentra Urgent Care - Houston Midtown", "facility_type": "concentra", "address": "3100 Main St", "city": "Houston", "state": "TX", "zip_code": "77002", "phone": "(713) 555-0301", "latitude": 29.7410, "longitude": -95.3810, "hours": "Mon-Fri 8AM-5PM, Sat 9AM-1PM", "accepts_walk_ins": True, "services": "DOT physicals, drug testing, pre-employment screening, workers comp", "network": "Concentra", "is_verified": True},
    {"name": "Any Lab Test Now - Austin", "facility_type": "lab", "address": "6507 Jester Blvd, Suite 303", "city": "Austin", "state": "TX", "zip_code": "78750", "phone": "(512) 555-0106", "latitude": 30.3900, "longitude": -97.7900, "hours": "Mon-Fri 9AM-5PM", "accepts_walk_ins": True, "services": "Drug testing, lab work, paternity testing", "network": "Any Lab Test Now", "is_verified": True},
]

PROVIDER_INFO = [
    {
        "provider": "checkr",
        "name": "Checkr",
        "description": "AI-powered background check platform trusted by 100,000+ companies",
        "website": "https://checkr.com",
        "packages": [
            {"name": "Basic", "price_range": "$29.99-$54.99", "includes": ["SSN Trace", "National Criminal Search", "Sex Offender Registry"]},
            {"name": "Standard", "price_range": "$54.99-$79.99", "includes": ["SSN Trace", "National Criminal Search", "Sex Offender Registry", "County Criminal Search", "Federal Criminal Search"]},
            {"name": "Professional", "price_range": "$79.99-$129.99", "includes": ["SSN Trace", "National Criminal Search", "Sex Offender Registry", "County Criminal Search", "Federal Criminal Search", "Employment Verification", "Education Verification"]},
        ],
        "turnaround": "1-3 business days",
        "integration": True,
    },
    {
        "provider": "crimshield",
        "name": "CrimShield",
        "description": "Background screening specifically designed for the telecom and utility industries",
        "website": "https://crimshield.com",
        "packages": [
            {"name": "Telecom Basic", "price_range": "$39.99-$59.99", "includes": ["SSN Trace", "National Criminal Search", "Sex Offender Registry", "Telecom Industry Check"]},
            {"name": "Telecom Complete", "price_range": "$69.99-$99.99", "includes": ["SSN Trace", "National Criminal Search", "County Criminal Search", "Federal Criminal Search", "Telecom Industry Check", "MVR"]},
            {"name": "Enterprise", "price_range": "$99.99-$149.99", "includes": ["Full Background", "Drug Screen Coordination", "MVR", "Employment Verification", "Telecom Certification Check"]},
        ],
        "turnaround": "2-5 business days",
        "integration": True,
    },
    {
        "provider": "sterling",
        "name": "Sterling",
        "description": "Global background and identity verification leader",
        "website": "https://sterlingcheck.com",
        "packages": [
            {"name": "Essential", "price_range": "$34.99-$64.99", "includes": ["Identity Verification", "Criminal Search", "Sex Offender Registry"]},
            {"name": "Advantage", "price_range": "$64.99-$99.99", "includes": ["Identity Verification", "Criminal Search", "County Search", "Employment Verification"]},
            {"name": "Complete", "price_range": "$99.99-$159.99", "includes": ["Full Identity Check", "Comprehensive Criminal", "Education & Employment Verification", "Professional License", "Credit Check"]},
        ],
        "turnaround": "2-4 business days",
        "integration": True,
    },
    {
        "provider": "hireright",
        "name": "HireRight",
        "description": "Enterprise-grade background screening with global coverage",
        "website": "https://hireright.com",
        "packages": [
            {"name": "Standard", "price_range": "$39.99-$69.99", "includes": ["SSN Trace", "Criminal Database Search", "Sex Offender Registry"]},
            {"name": "Enhanced", "price_range": "$69.99-$109.99", "includes": ["SSN Trace", "Criminal Database Search", "County Criminal", "Federal Criminal", "MVR"]},
            {"name": "Premium", "price_range": "$109.99-$179.99", "includes": ["Full Background", "Global Sanctions", "Employment History", "Education", "Professional References", "Drug Test Coordination"]},
        ],
        "turnaround": "2-5 business days",
        "integration": True,
    },
    {
        "provider": "goodhire",
        "name": "GoodHire",
        "description": "Simple, affordable background checks for small to mid-size businesses",
        "website": "https://goodhire.com",
        "packages": [
            {"name": "Basic", "price_range": "$29.99-$49.99", "includes": ["SSN Trace", "National Criminal Search", "Sex Offender Registry"]},
            {"name": "Standard", "price_range": "$49.99-$79.99", "includes": ["SSN Trace", "National Criminal Search", "County Criminal", "Federal Criminal", "Sex Offender Registry"]},
            {"name": "Premium", "price_range": "$79.99-$119.99", "includes": ["Full Background", "Employment Verification", "Education Verification", "MVR"]},
        ],
        "turnaround": "1-3 business days",
        "integration": False,
    },
    {
        "provider": "accurate",
        "name": "Accurate Background",
        "description": "Comprehensive employment screening with industry-specific solutions",
        "website": "https://accuratebackground.com",
        "packages": [
            {"name": "Quick Check", "price_range": "$24.99-$44.99", "includes": ["SSN Trace", "National Criminal", "Sex Offender Registry"]},
            {"name": "Standard", "price_range": "$44.99-$74.99", "includes": ["SSN Trace", "National Criminal", "County Criminal", "Federal Criminal"]},
            {"name": "Comprehensive", "price_range": "$74.99-$134.99", "includes": ["Full Criminal Background", "Employment Verification", "Education Verification", "Professional License", "MVR"]},
        ],
        "turnaround": "1-3 business days",
        "integration": True,
    },
]


@router.get("/stats")
def get_screening_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    pending = db.query(func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id,
        ScreeningRequest.status == ScreeningStatus.PENDING
    ).scalar() or 0

    in_progress = db.query(func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id,
        ScreeningRequest.status == ScreeningStatus.IN_PROGRESS
    ).scalar() or 0

    completed = db.query(func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id,
        ScreeningRequest.status == ScreeningStatus.COMPLETED
    ).scalar() or 0

    failed = db.query(func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id,
        ScreeningRequest.status == ScreeningStatus.FAILED
    ).scalar() or 0

    total_resolved = completed + failed
    pass_rate = round((completed / total_resolved * 100), 1) if total_resolved > 0 else 0

    total = db.query(func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id
    ).scalar() or 0

    pending_drug = db.query(func.count(DrugScreenAppointment.id)).filter(
        DrugScreenAppointment.org_id == org_id,
        DrugScreenAppointment.status.in_(["scheduled", "pending"])
    ).scalar() or 0

    by_provider = {}
    prov_rows = db.query(ScreeningRequest.provider, func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id
    ).group_by(ScreeningRequest.provider).all()
    for p, c in prov_rows:
        by_provider[p.value if hasattr(p, 'value') else str(p)] = c

    by_type = {}
    type_rows = db.query(ScreeningRequest.screening_type, func.count(ScreeningRequest.id)).filter(
        ScreeningRequest.org_id == org_id
    ).group_by(ScreeningRequest.screening_type).all()
    for t, c in type_rows:
        by_type[t] = c

    return {
        "pending_screenings": pending,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed,
        "total": total,
        "pass_rate": pass_rate,
        "pending_drug_tests": pending_drug,
        "by_provider": by_provider,
        "by_type": by_type,
    }


@router.post("/request")
def create_screening_request(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    candidate_id = data.get("user_id")
    if not candidate_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    candidate = db.query(User).filter(User.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")

    req = ScreeningRequest(
        org_id=org_id,
        user_id=candidate_id,
        screening_type=data.get("screening_type", "background_check"),
        provider=data.get("provider", "checkr"),
        package_name=data.get("package_name"),
        cost=float(data["cost"]) if data.get("cost") else None,
        requested_by=user.id,
        notes=data.get("notes"),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    return {
        "id": req.id,
        "screening_type": req.screening_type,
        "provider": req.provider.value if hasattr(req.provider, 'value') else str(req.provider),
        "status": req.status.value if hasattr(req.status, 'value') else str(req.status),
        "created_at": str(req.created_at),
    }


@router.get("/requests")
def list_screening_requests(
    status: str = Query(None),
    screening_type: str = Query(None),
    provider: str = Query(None),
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(ScreeningRequest).filter(ScreeningRequest.org_id == org_id)
    if status:
        q = q.filter(ScreeningRequest.status == status)
    if screening_type:
        q = q.filter(ScreeningRequest.screening_type == screening_type)
    if provider:
        q = q.filter(ScreeningRequest.provider == provider)
    if user_id:
        q = q.filter(ScreeningRequest.user_id == user_id)

    requests = q.order_by(desc(ScreeningRequest.created_at)).all()

    return [{
        "id": r.id,
        "org_id": r.org_id,
        "user_id": r.user_id,
        "candidate_name": r.candidate.full_name if r.candidate else None,
        "screening_type": r.screening_type,
        "provider": r.provider.value if hasattr(r.provider, 'value') else str(r.provider),
        "provider_request_id": r.provider_request_id,
        "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
        "package_name": r.package_name,
        "requested_date": str(r.requested_date) if r.requested_date else None,
        "completed_date": str(r.completed_date) if r.completed_date else None,
        "result": r.result,
        "result_details": r.result_details,
        "report_url": r.report_url,
        "adjudication": r.adjudication,
        "cost": float(r.cost) if r.cost else None,
        "requested_by": r.requested_by,
        "requester_name": r.requester.full_name if r.requester else None,
        "notes": r.notes,
        "created_at": str(r.created_at) if r.created_at else None,
        "updated_at": str(r.updated_at) if r.updated_at else None,
    } for r in requests]


@router.get("/requests/{request_id}")
def get_screening_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    r = db.query(ScreeningRequest).filter(
        ScreeningRequest.id == request_id,
        ScreeningRequest.org_id == org_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Screening request not found")

    return {
        "id": r.id,
        "org_id": r.org_id,
        "user_id": r.user_id,
        "candidate_name": r.candidate.full_name if r.candidate else None,
        "screening_type": r.screening_type,
        "provider": r.provider.value if hasattr(r.provider, 'value') else str(r.provider),
        "provider_request_id": r.provider_request_id,
        "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
        "package_name": r.package_name,
        "requested_date": str(r.requested_date) if r.requested_date else None,
        "completed_date": str(r.completed_date) if r.completed_date else None,
        "result": r.result,
        "result_details": r.result_details,
        "report_url": r.report_url,
        "adjudication": r.adjudication,
        "cost": float(r.cost) if r.cost else None,
        "requested_by": r.requested_by,
        "requester_name": r.requester.full_name if r.requester else None,
        "notes": r.notes,
        "created_at": str(r.created_at) if r.created_at else None,
        "updated_at": str(r.updated_at) if r.updated_at else None,
    }


@router.put("/requests/{request_id}/status")
def update_screening_status(request_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    r = db.query(ScreeningRequest).filter(
        ScreeningRequest.id == request_id,
        ScreeningRequest.org_id == org_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Screening request not found")

    new_status = data.get("status")
    if new_status:
        r.status = new_status
    if data.get("result"):
        r.result = data["result"]
    if data.get("result_details"):
        r.result_details = data["result_details"]
    if data.get("report_url"):
        r.report_url = data["report_url"]
    if data.get("adjudication"):
        r.adjudication = data["adjudication"]
    if data.get("provider_request_id"):
        r.provider_request_id = data["provider_request_id"]

    if new_status in ("completed", "failed"):
        r.completed_date = datetime.utcnow()

    db.commit()
    db.refresh(r)

    return {
        "ok": True,
        "id": r.id,
        "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
        "result": r.result,
        "completed_date": str(r.completed_date) if r.completed_date else None,
    }


@router.get("/providers")
def list_providers(user: User = Depends(get_current_user)):
    return PROVIDER_INFO


@router.get("/facilities/search")
def search_facilities(
    zip: str = Query(..., description="ZIP code to search near"),
    radius: float = Query(25, description="Search radius in miles"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    search_lat, search_lon = None, None
    if zip in ZIP_COORDS:
        search_lat, search_lon = ZIP_COORDS[zip]
    else:
        try:
            zip_num = int(zip[:3])
            if 100 <= zip_num <= 999:
                search_lat = 30.0 + (zip_num - 700) * 0.05
                search_lon = -97.0 - (zip_num - 700) * 0.02
        except (ValueError, IndexError):
            pass

    if search_lat is None:
        search_lat, search_lon = 30.2672, -97.7431

    db_facilities = db.query(DrugScreenFacility).all()

    if not db_facilities:
        for sf in SAMPLE_FACILITIES:
            fac = DrugScreenFacility(**sf)
            db.add(fac)
        db.commit()
        db_facilities = db.query(DrugScreenFacility).all()

    results = []
    for f in db_facilities:
        if f.latitude and f.longitude:
            dist = _haversine(search_lat, search_lon, f.latitude, f.longitude)
            if dist <= radius:
                results.append({
                    "id": f.id,
                    "name": f.name,
                    "facility_type": f.facility_type,
                    "address": f.address,
                    "city": f.city,
                    "state": f.state,
                    "zip_code": f.zip_code,
                    "phone": f.phone,
                    "fax": f.fax,
                    "email": f.email,
                    "website": f.website,
                    "latitude": f.latitude,
                    "longitude": f.longitude,
                    "hours": f.hours,
                    "accepts_walk_ins": f.accepts_walk_ins,
                    "services": f.services,
                    "network": f.network,
                    "is_verified": f.is_verified,
                    "distance_miles": round(dist, 1),
                })

    results.sort(key=lambda x: x["distance_miles"])

    return {
        "search_zip": zip,
        "search_radius": radius,
        "search_lat": search_lat,
        "search_lon": search_lon,
        "total_results": len(results),
        "facilities": results,
    }


@router.post("/facilities")
def add_facility(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_user_org(db, user)

    fac = DrugScreenFacility(
        name=data["name"],
        facility_type=data.get("facility_type", "other"),
        address=data["address"],
        city=data["city"],
        state=data["state"],
        zip_code=data["zip_code"],
        phone=data.get("phone"),
        fax=data.get("fax"),
        email=data.get("email"),
        website=data.get("website"),
        latitude=float(data["latitude"]) if data.get("latitude") else None,
        longitude=float(data["longitude"]) if data.get("longitude") else None,
        hours=data.get("hours"),
        accepts_walk_ins=data.get("accepts_walk_ins", True),
        services=data.get("services"),
        network=data.get("network"),
        is_verified=data.get("is_verified", False),
    )
    db.add(fac)
    db.commit()
    db.refresh(fac)

    return {
        "id": fac.id,
        "name": fac.name,
        "city": fac.city,
        "state": fac.state,
        "zip_code": fac.zip_code,
    }


@router.get("/facilities/{facility_id}")
def get_facility(facility_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fac = db.query(DrugScreenFacility).filter(DrugScreenFacility.id == facility_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")

    return {
        "id": fac.id,
        "name": fac.name,
        "facility_type": fac.facility_type,
        "address": fac.address,
        "city": fac.city,
        "state": fac.state,
        "zip_code": fac.zip_code,
        "phone": fac.phone,
        "fax": fac.fax,
        "email": fac.email,
        "website": fac.website,
        "latitude": fac.latitude,
        "longitude": fac.longitude,
        "hours": fac.hours,
        "accepts_walk_ins": fac.accepts_walk_ins,
        "services": fac.services,
        "network": fac.network,
        "is_verified": fac.is_verified,
        "last_verified": str(fac.last_verified) if fac.last_verified else None,
        "created_at": str(fac.created_at) if fac.created_at else None,
        "updated_at": str(fac.updated_at) if fac.updated_at else None,
    }


@router.post("/appointments")
def schedule_appointment(data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)

    candidate_id = data.get("user_id")
    facility_id = data.get("facility_id")
    scheduled_date = data.get("scheduled_date")

    if not candidate_id or not facility_id or not scheduled_date:
        raise HTTPException(status_code=400, detail="user_id, facility_id, and scheduled_date are required")

    fac = db.query(DrugScreenFacility).filter(DrugScreenFacility.id == facility_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")

    appt = DrugScreenAppointment(
        org_id=org_id,
        user_id=candidate_id,
        facility_id=facility_id,
        screening_request_id=data.get("screening_request_id"),
        test_type=data.get("test_type", "urine_5_panel"),
        scheduled_date=datetime.fromisoformat(scheduled_date),
        status="scheduled",
        chain_of_custody_number=data.get("chain_of_custody_number"),
        mro_name=data.get("mro_name"),
        notes=data.get("notes"),
        created_by=user.id,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    return {
        "id": appt.id,
        "user_id": appt.user_id,
        "facility_id": appt.facility_id,
        "facility_name": fac.name,
        "scheduled_date": str(appt.scheduled_date),
        "status": appt.status,
        "test_type": appt.test_type,
    }


@router.get("/appointments")
def list_appointments(
    status: str = Query(None),
    user_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = _get_user_org(db, user)
    q = db.query(DrugScreenAppointment).filter(DrugScreenAppointment.org_id == org_id)
    if status:
        q = q.filter(DrugScreenAppointment.status == status)
    if user_id:
        q = q.filter(DrugScreenAppointment.user_id == user_id)

    appts = q.order_by(desc(DrugScreenAppointment.scheduled_date)).all()

    return [{
        "id": a.id,
        "org_id": a.org_id,
        "user_id": a.user_id,
        "candidate_name": a.candidate.full_name if a.candidate else None,
        "facility_id": a.facility_id,
        "facility_name": a.facility.name if a.facility else None,
        "facility_address": a.facility.address if a.facility else None,
        "screening_request_id": a.screening_request_id,
        "test_type": a.test_type,
        "scheduled_date": str(a.scheduled_date) if a.scheduled_date else None,
        "status": a.status,
        "result": a.result,
        "result_date": str(a.result_date) if a.result_date else None,
        "chain_of_custody_number": a.chain_of_custody_number,
        "mro_name": a.mro_name,
        "notes": a.notes,
        "created_by": a.created_by,
        "creator_name": a.creator.full_name if a.creator else None,
        "created_at": str(a.created_at) if a.created_at else None,
        "updated_at": str(a.updated_at) if a.updated_at else None,
    } for a in appts]


@router.put("/appointments/{appointment_id}")
def update_appointment(appointment_id: str, data: dict = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = _get_user_org(db, user)
    appt = db.query(DrugScreenAppointment).filter(
        DrugScreenAppointment.id == appointment_id,
        DrugScreenAppointment.org_id == org_id
    ).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if "status" in data:
        appt.status = data["status"]
    if "result" in data:
        appt.result = data["result"]
        appt.result_date = datetime.utcnow()
    if "scheduled_date" in data:
        appt.scheduled_date = datetime.fromisoformat(data["scheduled_date"])
    if "chain_of_custody_number" in data:
        appt.chain_of_custody_number = data["chain_of_custody_number"]
    if "mro_name" in data:
        appt.mro_name = data["mro_name"]
    if "notes" in data:
        appt.notes = data["notes"]
    if "test_type" in data:
        appt.test_type = data["test_type"]

    db.commit()
    db.refresh(appt)

    return {
        "ok": True,
        "id": appt.id,
        "status": appt.status,
        "result": appt.result,
        "result_date": str(appt.result_date) if appt.result_date else None,
    }
