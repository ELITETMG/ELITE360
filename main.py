from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from app.db.session import engine
from app.models.base import Base
from app.models.models import (
    Org, User, OrgMember, Project, WorkPackage, TaskType, Task,
    FieldEntry, AuditLog, Attachment, InspectionTemplate, Inspection,
    AssetCategory, Asset, FleetVehicle, TechnicianLocation,
    SafetyIncident, SafetyInspectionTemplate, SafetyInspectionRecord,
    ToolboxTalk, ToolboxTalkAttendance, SafetyTraining, PPECompliance,
    CorrectiveAction, OSHALog, SafetyDocument,
    EmployeeProfile, TimeEntry, PTORequest, OnboardingChecklist,
    OnboardingTask, PerformanceReview, HRTrainingRecord,
    EmployeeDocument, CompensationRecord, SkillEntry
)
from app.api import auth, projects, tasks, work_packages, task_types, orgs, dashboard, attachments, inspections, reports
from app.api.materials import router as materials_router
from app.api.activities import router as activities_router
from app.api.documents import router as documents_router
from app.api.budget import router as budget_router
from app.api.map_views import router as map_views_router
from app.api.analysis import router as analysis_router
from app.api.ai import router as ai_router
from app.api.integrations import router as integrations_router
from app.api.admin import router as admin_router
from app.api.billing import router as billing_router
from app.api.dispatch import router as dispatch_router
from app.api.assets import router as assets_router
from app.api.fleet import router as fleet_router
from app.api.safety import router as safety_router
from app.api.hr import router as hr_router
from app.api.accounting import router as accounting_router
from app.api.payroll import router as payroll_router
from app.api.onboarding import router as onboarding_router
from app.api.screening import router as screening_router
from app.api.crm import router as crm_router

app = FastAPI(title="Elite Technician Management Group", version="0.2.0")

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

app.add_middleware(NoCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(work_packages.router)
app.include_router(task_types.router)
app.include_router(orgs.router)
app.include_router(dashboard.router)
app.include_router(attachments.router)
app.include_router(inspections.router)
app.include_router(reports.router)
app.include_router(materials_router)
app.include_router(activities_router)
app.include_router(documents_router)
app.include_router(budget_router)
app.include_router(map_views_router)
app.include_router(analysis_router)
app.include_router(ai_router)
app.include_router(integrations_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(dispatch_router)
app.include_router(assets_router)
app.include_router(fleet_router)
app.include_router(safety_router)
app.include_router(hr_router)
app.include_router(accounting_router)
app.include_router(payroll_router)
app.include_router(onboarding_router)
app.include_router(screening_router)
app.include_router(crm_router)


@app.on_event("startup")
def startup():
    import os
    os.makedirs("app/static/uploads", exist_ok=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _seed_defaults()


def _seed_defaults():
    from app.db.session import SessionLocal
    from app.core.auth import hash_password
    from datetime import datetime, timedelta
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            org = Org(name="Demo Contractor", org_type="contractor")
            db.add(org)
            db.flush()

            admin = User(
                email="admin@ftth.com",
                hashed_password=hash_password("admin123"),
                full_name="Admin User"
            )
            db.add(admin)
            db.flush()

            db.add(OrgMember(org_id=org.id, user_id=admin.id, role="org_admin"))

            tt1 = TaskType(name="Aerial Fiber", unit="feet", color="#3B82F6")
            tt2 = TaskType(name="Underground Conduit", unit="feet", color="#10B981")
            tt3 = TaskType(name="Drop Installation", unit="count", color="#F59E0B")
            tt4 = TaskType(name="Splice Point", unit="count", color="#EF4444")
            tt5 = TaskType(name="Handhole/Vault", unit="count", color="#8B5CF6")
            db.add_all([tt1, tt2, tt3, tt4, tt5])
            db.flush()

            it1 = InspectionTemplate(name="Aerial Fiber QC", task_type_id=tt1.id,
                checklist_items='["Strand tension verified","Lashing wire secure","Proper sag maintained","No visible damage","Hardware tight"]',
                require_photos=True)
            it2 = InspectionTemplate(name="Underground Conduit QC", task_type_id=tt2.id,
                checklist_items='["Conduit depth verified","Backfill compacted","Locate wire installed","Sweep test passed","Endcaps installed"]',
                require_photos=True)
            it3 = InspectionTemplate(name="Drop Installation QC", task_type_id=tt3.id,
                checklist_items='["NID mounted properly","Cable secured","Drip loop present","Signal level verified","Customer acceptance"]',
                require_photos=False)
            db.add_all([it1, it2, it3])

            project = Project(
                name="Greenfield FTTH Build - Phase 1",
                description="Initial fiber deployment covering the downtown district",
                executing_org_id=org.id,
                status="active"
            )
            db.add(project)
            db.flush()

            wp = WorkPackage(project_id=project.id, name="Zone A - Main Corridor")
            db.add(wp)
            db.flush()

            from geoalchemy2.functions import ST_GeomFromGeoJSON
            import json

            tasks_data = [
                {"name": "Main trunk - Oak St", "tt": tt1, "qty": 2400, "actual": 2400, "status": "approved", "geom": {"type": "LineString", "coordinates": [[-97.7431, 30.2672], [-97.7401, 30.2692]]}},
                {"name": "Main trunk - Elm Ave", "tt": tt1, "qty": 1800, "actual": 1200, "status": "in_progress", "geom": {"type": "LineString", "coordinates": [[-97.7401, 30.2692], [-97.7371, 30.2682]]}},
                {"name": "Conduit run - 5th St", "tt": tt2, "qty": 3200, "actual": 3200, "status": "submitted", "geom": {"type": "LineString", "coordinates": [[-97.7431, 30.2672], [-97.7431, 30.2642]]}},
                {"name": "Conduit run - 6th St", "tt": tt2, "qty": 2100, "actual": 0, "status": "not_started", "geom": {"type": "LineString", "coordinates": [[-97.7421, 30.2642], [-97.7421, 30.2622]]}},
                {"name": "Splice closure SC-01", "tt": tt4, "qty": 1, "actual": 1, "status": "approved", "geom": {"type": "Point", "coordinates": [-97.7401, 30.2692]}},
                {"name": "Splice closure SC-02", "tt": tt4, "qty": 1, "actual": 0, "status": "not_started", "geom": {"type": "Point", "coordinates": [-97.7371, 30.2682]}},
                {"name": "Handhole HH-01", "tt": tt5, "qty": 1, "actual": 1, "status": "billed", "geom": {"type": "Point", "coordinates": [-97.7431, 30.2672]}},
                {"name": "Handhole HH-02", "tt": tt5, "qty": 1, "actual": 1, "status": "approved", "geom": {"type": "Point", "coordinates": [-97.7431, 30.2642]}},
                {"name": "Drop - 123 Oak St", "tt": tt3, "qty": 1, "actual": 1, "status": "approved", "geom": {"type": "Point", "coordinates": [-97.7421, 30.2677]}},
                {"name": "Drop - 125 Oak St", "tt": tt3, "qty": 1, "actual": 0, "status": "in_progress", "geom": {"type": "Point", "coordinates": [-97.7415, 30.2680]}},
                {"name": "Drop - 200 Elm Ave", "tt": tt3, "qty": 1, "actual": 0, "status": "not_started", "geom": {"type": "Point", "coordinates": [-97.7388, 30.2686]}},
                {"name": "Drop - 202 Elm Ave", "tt": tt3, "qty": 1, "actual": 1, "status": "submitted", "geom": {"type": "Point", "coordinates": [-97.7383, 30.2684]}},
                {"name": "Branch fiber - Pine Rd", "tt": tt1, "qty": 950, "actual": 400, "status": "in_progress", "geom": {"type": "LineString", "coordinates": [[-97.7401, 30.2692], [-97.7391, 30.2712]]}},
                {"name": "Branch fiber - Cedar Ln", "tt": tt1, "qty": 1100, "actual": 0, "status": "rework", "geom": {"type": "LineString", "coordinates": [[-97.7371, 30.2682], [-97.7361, 30.2662]]}},
            ]

            for td in tasks_data:
                t = Task(
                    name=td["name"], project_id=project.id,
                    work_package_id=wp.id, task_type_id=td["tt"].id,
                    planned_qty=td["qty"], actual_qty=td.get("actual", 0),
                    unit=td["tt"].unit, status=td.get("status", "not_started"),
                    geometry=ST_GeomFromGeoJSON(json.dumps(td["geom"]))
                )
                db.add(t)

            db.commit()

        if db.query(AssetCategory).count() == 0:
            org = db.query(Org).first()
            if org:
                cats = [
                    AssetCategory(org_id=org.id, name="Vehicles", icon="truck", color="#3B82F6"),
                    AssetCategory(org_id=org.id, name="Tools & Equipment", icon="wrench", color="#10B981"),
                    AssetCategory(org_id=org.id, name="Test Equipment", icon="gauge", color="#F59E0B"),
                    AssetCategory(org_id=org.id, name="Fiber Optic Equipment", icon="cable", color="#8B5CF6"),
                    AssetCategory(org_id=org.id, name="Safety Equipment", icon="shield", color="#EF4444"),
                    AssetCategory(org_id=org.id, name="IT Equipment", icon="laptop", color="#06B6D4"),
                ]
                db.add_all(cats)
                db.flush()

                admin = db.query(User).first()
                assets_data = [
                    {"name": "OTDR Yokogawa AQ7280", "cat": cats[2], "tag": "AST-001", "serial": "YK7280-A1234", "make": "Yokogawa", "model": "AQ7280", "cost": 12500, "value": 9800, "status": "in_use", "condition": "good"},
                    {"name": "Fusion Splicer Fujikura 90S+", "cat": cats[3], "tag": "AST-002", "serial": "FJ90S-B5678", "make": "Fujikura", "model": "90S+", "cost": 18000, "value": 14500, "status": "assigned", "condition": "good"},
                    {"name": "Power Meter EXFO FPM-300", "cat": cats[2], "tag": "AST-003", "serial": "EX300-C9012", "make": "EXFO", "model": "FPM-300", "cost": 2200, "value": 1800, "status": "available", "condition": "good"},
                    {"name": "Fiber Cleaver Sumitomo FC-6RS", "cat": cats[3], "tag": "AST-004", "serial": "SM6RS-D3456", "make": "Sumitomo", "model": "FC-6RS", "cost": 1500, "value": 1100, "status": "in_use", "condition": "fair"},
                    {"name": "Cable Locator Vivax vLoc3-Pro", "cat": cats[1], "tag": "AST-005", "serial": "VX3P-E7890", "make": "Vivax", "model": "vLoc3-Pro", "cost": 3800, "value": 2900, "status": "available", "condition": "good"},
                    {"name": "Bucket Truck #101", "cat": cats[0], "tag": "VEH-101", "serial": "1HTWNAZT4HH123456", "make": "International", "model": "4300 Bucket", "cost": 95000, "value": 72000, "status": "in_use", "condition": "good"},
                    {"name": "Service Van #201", "cat": cats[0], "tag": "VEH-201", "serial": "1FTBW2CM9HKA98765", "make": "Ford", "model": "Transit 250", "cost": 42000, "value": 34000, "status": "assigned", "condition": "good"},
                    {"name": "Trencher Vermeer RTX250", "cat": cats[1], "tag": "AST-006", "serial": "VR250-F2345", "make": "Vermeer", "model": "RTX250", "cost": 55000, "value": 41000, "status": "available", "condition": "good"},
                    {"name": "Safety Harness Kit (Set of 4)", "cat": cats[4], "tag": "SAF-001", "serial": "SH-G6789", "make": "3M", "model": "DBI-SALA", "cost": 1200, "value": 900, "status": "in_use", "condition": "good"},
                    {"name": "Rugged Tablet Samsung Galaxy Tab Active4 Pro", "cat": cats[5], "tag": "IT-001", "serial": "SGTA4-H0123", "make": "Samsung", "model": "Galaxy Tab Active4 Pro", "cost": 650, "value": 480, "status": "assigned", "condition": "good"},
                ]
                for ad in assets_data:
                    a = Asset(
                        org_id=org.id, category_id=ad["cat"].id, name=ad["name"],
                        asset_tag=ad["tag"], serial_number=ad["serial"],
                        make=ad["make"], model=ad["model"],
                        purchase_cost=ad["cost"], current_value=ad["value"],
                        status=ad["status"], condition=ad["condition"],
                        useful_life_years=5, depreciation_method="straight_line",
                    )
                    db.add(a)
                db.flush()

                vehicles_data = [
                    {"name": "Bucket Truck #101", "make": "International", "model": "4300", "year": 2022, "plate": "TX-BTK-101", "type": "bucket_truck", "odo": 45200, "fuel": 72, "lat": 30.2672, "lng": -97.7431},
                    {"name": "Service Van #201", "make": "Ford", "model": "Transit 250", "year": 2023, "plate": "TX-VAN-201", "type": "van", "odo": 28100, "fuel": 85, "lat": 30.2692, "lng": -97.7401},
                    {"name": "Pickup Truck #301", "make": "Chevrolet", "model": "Silverado 2500HD", "year": 2023, "plate": "TX-PKU-301", "type": "pickup", "odo": 31500, "fuel": 60, "lat": 30.2660, "lng": -97.7420},
                    {"name": "Splice Van #202", "make": "Ford", "model": "E-350", "year": 2021, "plate": "TX-SPL-202", "type": "van", "odo": 52300, "fuel": 45, "lat": 30.2710, "lng": -97.7390},
                    {"name": "Mini Excavator Trailer #401", "make": "CAT", "model": "301.7", "year": 2022, "plate": "TX-EXC-401", "type": "trailer", "odo": 1200, "fuel": None, "lat": 30.2645, "lng": -97.7450},
                ]
                for vd in vehicles_data:
                    fv = FleetVehicle(
                        org_id=org.id, name=vd["name"], make=vd["make"], model=vd["model"],
                        year=vd["year"], license_plate=vd["plate"], vehicle_type=vd["type"],
                        odometer=vd["odo"], fuel_level=vd["fuel"],
                        current_lat=vd["lat"], current_lng=vd["lng"],
                        last_location_update=datetime.utcnow(),
                    )
                    db.add(fv)

                tech_loc = TechnicianLocation(
                    user_id=admin.id, org_id=org.id,
                    lat=30.2672, lng=-97.7431,
                    source="mobile_checkin", is_active=True,
                )
                db.add(tech_loc)
                db.commit()

        if db.query(SafetyIncident).count() == 0:
            org = db.query(Org).first()
            admin = db.query(User).first()
            project = db.query(Project).first()
            if org and admin:
                now = datetime.utcnow()

                incidents = [
                    SafetyIncident(org_id=org.id, reported_by=admin.id, project_id=project.id if project else None,
                        incident_type="slip_trip_fall", severity="medium", status="closed", title="Slip on wet surface near handhole HH-02",
                        description="Technician slipped on wet grass while accessing handhole. Minor knee abrasion. First aid applied on site.",
                        occurred_at=now - timedelta(days=45), location_description="Handhole HH-02, 5th St",
                        is_near_miss=False, is_osha_recordable=False, injury_type="abrasion", body_part="knee",
                        root_cause="Wet conditions, no slip-resistant footwear", immediate_actions="Applied first aid, area marked"),
                    SafetyIncident(org_id=org.id, reported_by=admin.id, project_id=project.id if project else None,
                        incident_type="struck_by", severity="high", status="corrective_action", title="Near miss - falling branch near aerial crew",
                        description="Tree branch fell approximately 3 feet from aerial crew member during strand installation. No injuries.",
                        occurred_at=now - timedelta(days=20), location_description="Oak St, Span 3",
                        is_near_miss=True, is_osha_recordable=False,
                        root_cause="Dead branch not identified during pre-work survey", immediate_actions="Work stopped, arborist called"),
                    SafetyIncident(org_id=org.id, reported_by=admin.id, project_id=project.id if project else None,
                        incident_type="electrical", severity="critical", status="investigating", title="Electrical contact during conduit boring",
                        description="Boring crew hit unmarked underground electrical line. Equipment damaged, no personnel injuries due to proper grounding.",
                        occurred_at=now - timedelta(days=5), location_description="6th St, near utility crossing",
                        is_near_miss=False, is_osha_recordable=True, medical_treatment=False,
                        root_cause="Unmarked utility line", immediate_actions="Emergency shutdown, utility company notified, 811 re-locate requested"),
                    SafetyIncident(org_id=org.id, reported_by=admin.id,
                        incident_type="ergonomic", severity="low", status="closed", title="Repetitive strain - splice technician",
                        description="Splice tech reported wrist discomfort after extended splicing session. Ergonomic tools issued.",
                        occurred_at=now - timedelta(days=60), is_near_miss=False, is_osha_recordable=False,
                        injury_type="strain", body_part="wrist", root_cause="Extended repetitive motion without breaks"),
                    SafetyIncident(org_id=org.id, reported_by=admin.id,
                        incident_type="vehicle", severity="medium", status="closed", title="Near miss - backing incident at job site",
                        description="Service van nearly struck a pedestrian while backing into work zone. Spotter was not deployed.",
                        occurred_at=now - timedelta(days=30), is_near_miss=True, is_osha_recordable=False,
                        root_cause="No spotter used for backing operation", immediate_actions="Implemented mandatory spotter policy"),
                ]
                db.add_all(incidents)
                db.flush()

                sit1 = SafetyInspectionTemplate(org_id=org.id, name="Daily Job Site Safety Inspection", category="job_site",
                    checklist_items='["Work zone properly marked with signs/cones","All crew wearing required PPE","Tools and equipment inspected","Locate tickets verified and on site","First aid kit stocked and accessible","Emergency contacts posted","Weather conditions assessed","Hazard communication signs posted","Fire extinguisher accessible","Housekeeping - area clean and organized"]',
                    frequency="daily")
                sit2 = SafetyInspectionTemplate(org_id=org.id, name="Aerial Work Safety Checklist", category="aerial",
                    checklist_items='["Bucket truck outriggers deployed on solid ground","Boom inspection completed","Fall protection harness inspected","Lanyard attached to approved anchor","Minimum approach distance maintained","Traffic control in place","Communication established with ground crew","Tools secured with tool lanyards","Hard hat and safety glasses worn","Weather conditions suitable for aerial work"]',
                    frequency="per_job")
                sit3 = SafetyInspectionTemplate(org_id=org.id, name="Confined Space Entry Checklist", category="confined_space",
                    checklist_items='["Permit obtained and posted","Atmospheric testing completed - O2/LEL/H2S/CO","Ventilation established","Rescue plan in place","Attendant stationed at entry","Communication system tested","Personal gas monitors calibrated","Entry/exit log maintained","Emergency equipment staged","All entrants trained and certified"]',
                    frequency="per_entry")
                db.add_all([sit1, sit2, sit3])
                db.flush()

                sir1 = SafetyInspectionRecord(org_id=org.id, template_id=sit1.id, inspector_id=admin.id,
                    project_id=project.id if project else None, status="passed", score=95.0,
                    checklist_results='{"items":[true,true,true,true,true,true,true,false,true,true]}',
                    findings="Hazard communication sign missing at east entrance - corrected on site",
                    conducted_at=now - timedelta(days=1))
                sir2 = SafetyInspectionRecord(org_id=org.id, template_id=sit2.id, inspector_id=admin.id,
                    project_id=project.id if project else None, status="passed", score=100.0,
                    checklist_results='{"items":[true,true,true,true,true,true,true,true,true,true]}',
                    conducted_at=now - timedelta(days=2))
                db.add_all([sir1, sir2])

                tt1 = ToolboxTalk(org_id=org.id, presenter_id=admin.id, project_id=project.id if project else None,
                    topic="Heat Stress Prevention", category="seasonal",
                    content="Discussed signs/symptoms of heat exhaustion and heat stroke. Reviewed hydration schedule, shade break requirements, and buddy system protocol for hot weather operations.",
                    duration_minutes=20, conducted_at=now - timedelta(days=3), attendee_count=6)
                tt2 = ToolboxTalk(org_id=org.id, presenter_id=admin.id,
                    topic="Trenching & Excavation Safety", category="construction",
                    content="Reviewed OSHA trenching standards, soil classification, protective systems, and daily inspection requirements. Emphasized the importance of calling 811 before every dig.",
                    duration_minutes=25, conducted_at=now - timedelta(days=10), attendee_count=8)
                tt3 = ToolboxTalk(org_id=org.id, presenter_id=admin.id,
                    topic="Distracted Driving Awareness", category="vehicle",
                    content="Discussed company cell phone policy, GPS usage guidelines, and pre-trip planning. Reviewed recent near-miss backing incident.",
                    duration_minutes=15, conducted_at=now - timedelta(days=17), attendee_count=12)
                db.add_all([tt1, tt2, tt3])
                db.flush()

                db.add(ToolboxTalkAttendance(talk_id=tt1.id, user_id=admin.id, attended=True))
                db.add(ToolboxTalkAttendance(talk_id=tt2.id, user_id=admin.id, attended=True))
                db.add(ToolboxTalkAttendance(talk_id=tt3.id, user_id=admin.id, attended=True))

                trainings = [
                    SafetyTraining(org_id=org.id, user_id=admin.id, training_name="OSHA 30-Hour Construction", training_type="osha",
                        provider="OSHA Training Institute", completion_date=now - timedelta(days=180), expiry_date=now + timedelta(days=1645),
                        certificate_number="OSHA30-2024-A1234", status="completed", hours=30),
                    SafetyTraining(org_id=org.id, user_id=admin.id, training_name="CPR/First Aid/AED", training_type="first_aid",
                        provider="American Red Cross", completion_date=now - timedelta(days=90), expiry_date=now + timedelta(days=640),
                        certificate_number="ARC-CPR-B5678", status="completed", hours=8),
                    SafetyTraining(org_id=org.id, user_id=admin.id, training_name="Confined Space Entry", training_type="confined_space",
                        provider="National Safety Council", completion_date=now - timedelta(days=365), expiry_date=now + timedelta(days=0),
                        certificate_number="NSC-CSE-C9012", status="expiring", hours=16),
                    SafetyTraining(org_id=org.id, user_id=admin.id, training_name="Aerial Lift Operator", training_type="equipment",
                        provider="Equipment Safety Training LLC", completion_date=now - timedelta(days=120), expiry_date=now + timedelta(days=975),
                        status="completed", hours=8),
                    SafetyTraining(org_id=org.id, user_id=admin.id, training_name="Flagger Certification", training_type="traffic_control",
                        provider="ATSSA", completion_date=now - timedelta(days=200), expiry_date=now + timedelta(days=895),
                        status="completed", hours=4),
                ]
                db.add_all(trainings)

                ppe_items = [
                    PPECompliance(org_id=org.id, user_id=admin.id, ppe_type="Hard Hat", status="compliant",
                        issued_at=now - timedelta(days=365), last_inspected_at=now - timedelta(days=7),
                        next_inspection_due=now + timedelta(days=83), condition="good", serial_number="HH-001"),
                    PPECompliance(org_id=org.id, user_id=admin.id, ppe_type="Safety Glasses", status="compliant",
                        issued_at=now - timedelta(days=90), last_inspected_at=now - timedelta(days=7),
                        condition="good"),
                    PPECompliance(org_id=org.id, user_id=admin.id, ppe_type="Hi-Vis Vest (Class 3)", status="compliant",
                        issued_at=now - timedelta(days=180), last_inspected_at=now - timedelta(days=14),
                        condition="good"),
                    PPECompliance(org_id=org.id, user_id=admin.id, ppe_type="Fall Protection Harness", status="needs_inspection",
                        issued_at=now - timedelta(days=400), last_inspected_at=now - timedelta(days=95),
                        next_inspection_due=now - timedelta(days=5), condition="fair", serial_number="FPH-A101"),
                    PPECompliance(org_id=org.id, user_id=admin.id, ppe_type="Steel-Toe Boots", status="compliant",
                        issued_at=now - timedelta(days=120), condition="good"),
                    PPECompliance(org_id=org.id, user_id=admin.id, ppe_type="Cut-Resistant Gloves", status="replace",
                        issued_at=now - timedelta(days=200), last_inspected_at=now - timedelta(days=3),
                        condition="worn"),
                ]
                db.add_all(ppe_items)

                ca1 = CorrectiveAction(org_id=org.id, incident_id=incidents[1].id, assigned_to=admin.id,
                    title="Implement pre-work tree/vegetation survey", description="Develop and implement a mandatory pre-work vegetation assessment checklist for all aerial fiber installation jobs.",
                    action_type="corrective", priority="high", status="in_progress", due_date=now + timedelta(days=14),
                    root_cause_category="procedure")
                ca2 = CorrectiveAction(org_id=org.id, incident_id=incidents[2].id, assigned_to=admin.id,
                    title="Verify 811 locate accuracy protocol", description="Create a protocol requiring crew leads to physically verify locate marks against plans before starting any boring/excavation work.",
                    action_type="corrective", priority="critical", status="open", due_date=now + timedelta(days=7),
                    root_cause_category="procedure")
                ca3 = CorrectiveAction(org_id=org.id, incident_id=incidents[4].id, assigned_to=admin.id,
                    title="Mandatory spotter for all backing operations", description="Update vehicle operations policy to require a designated spotter for all backing maneuvers at job sites.",
                    action_type="preventive", priority="medium", status="completed", due_date=now - timedelta(days=5),
                    completed_at=now - timedelta(days=7), root_cause_category="training")
                db.add_all([ca1, ca2, ca3])

                osha1 = OSHALog(org_id=org.id, year=2025, total_hours_worked=156000, total_employees=32,
                    total_incidents=8, recordable_cases=2, dart_cases=1, fatalities=0,
                    trir=2.56, dart_rate=1.28, emr=0.92, days_away=3, days_restricted=5)
                osha2 = OSHALog(org_id=org.id, year=2024, total_hours_worked=148000, total_employees=28,
                    total_incidents=12, recordable_cases=4, dart_cases=2, fatalities=0,
                    trir=5.41, dart_rate=2.70, emr=1.05, days_away=8, days_restricted=12)
                db.add_all([osha1, osha2])

                safety_docs = [
                    SafetyDocument(org_id=org.id, title="Company Safety Manual 2025", category="manual",
                        description="Comprehensive safety policies and procedures manual", version="3.2",
                        effective_date=now - timedelta(days=30), review_date=now + timedelta(days=335), uploaded_by=admin.id),
                    SafetyDocument(org_id=org.id, title="Emergency Action Plan", category="emergency",
                        description="Site-specific emergency response procedures", version="2.0",
                        effective_date=now - timedelta(days=60), review_date=now + timedelta(days=305), uploaded_by=admin.id),
                    SafetyDocument(org_id=org.id, title="Hazard Communication Program", category="compliance",
                        description="OSHA HazCom standard compliance program with SDS management", version="1.5",
                        effective_date=now - timedelta(days=90), uploaded_by=admin.id),
                ]
                db.add_all(safety_docs)
                db.commit()

        if db.query(EmployeeProfile).count() == 0:
            org = db.query(Org).first()
            admin = db.query(User).first()
            if org and admin:
                now = datetime.utcnow()

                emp = EmployeeProfile(org_id=org.id, user_id=admin.id, employee_id="EMP-001",
                    job_title="Operations Manager", department="Operations", status="active",
                    hire_date=now - timedelta(days=1095), employment_type="full_time",
                    phone="(512) 555-0101", address="123 Main St", city="Austin", state="TX", zip_code="78701",
                    emergency_contact_name="Jane User", emergency_contact_phone="(512) 555-0199", emergency_contact_relation="Spouse",
                    drivers_license="TX12345678", dl_expiry=now + timedelta(days=730),
                    cdl_class="B", medical_card_expiry=now + timedelta(days=365),
                    shirt_size="L", boot_size="10.5",
                    pto_balance_vacation=80, pto_balance_sick=40, pto_balance_personal=16)
                db.add(emp)
                db.flush()

                time_entries = []
                for i in range(14):
                    day = now - timedelta(days=i)
                    if day.weekday() < 5:
                        te = TimeEntry(org_id=org.id, user_id=admin.id,
                            clock_in=day.replace(hour=6, minute=30),
                            clock_out=day.replace(hour=16, minute=0) if i > 0 else None,
                            break_minutes=30,
                            total_hours=9.0 if i > 0 else None,
                            overtime_hours=1.0 if i > 0 and day.weekday() in [0, 2, 4] else 0,
                            entry_type="regular", source="manual")
                        time_entries.append(te)
                db.add_all(time_entries)

                pto1 = PTORequest(org_id=org.id, user_id=admin.id, pto_type="vacation",
                    start_date=now + timedelta(days=30), end_date=now + timedelta(days=34),
                    total_days=5, status="pending", reason="Family vacation")
                pto2 = PTORequest(org_id=org.id, user_id=admin.id, pto_type="sick",
                    start_date=now - timedelta(days=15), end_date=now - timedelta(days=15),
                    total_days=1, status="approved", reason="Doctor appointment",
                    approver_id=admin.id, approved_at=now - timedelta(days=16))
                db.add_all([pto1, pto2])

                checklist = OnboardingChecklist(org_id=org.id, name="Field Technician Onboarding",
                    description="Standard onboarding checklist for new field technicians", department="Field Operations")
                db.add(checklist)
                db.flush()

                ob_tasks = [
                    OnboardingTask(checklist_id=checklist.id, title="Complete I-9 Employment Verification", category="HR Paperwork", due_days=3, sort_order=1),
                    OnboardingTask(checklist_id=checklist.id, title="Complete W-4 Tax Form", category="HR Paperwork", due_days=3, sort_order=2),
                    OnboardingTask(checklist_id=checklist.id, title="Enroll in Benefits", category="HR Paperwork", due_days=30, sort_order=3),
                    OnboardingTask(checklist_id=checklist.id, title="Issue PPE (hard hat, vest, glasses, gloves, boots)", category="Safety", due_days=1, sort_order=4),
                    OnboardingTask(checklist_id=checklist.id, title="Complete OSHA 10-Hour Training", category="Safety", due_days=14, sort_order=5),
                    OnboardingTask(checklist_id=checklist.id, title="Complete CPR/First Aid Certification", category="Safety", due_days=30, sort_order=6),
                    OnboardingTask(checklist_id=checklist.id, title="Fiber Optic Basics Training", category="Technical", due_days=7, sort_order=7),
                    OnboardingTask(checklist_id=checklist.id, title="OTDR Training and Certification", category="Technical", due_days=14, sort_order=8),
                    OnboardingTask(checklist_id=checklist.id, title="Vehicle Orientation & Driving Policy Review", category="Operations", due_days=3, sort_order=9),
                    OnboardingTask(checklist_id=checklist.id, title="IT Setup - Tablet, Email, Time Tracking App", category="IT", due_days=1, sort_order=10),
                    OnboardingTask(checklist_id=checklist.id, title="Ride-along with Senior Technician (3 days)", category="Field Training", due_days=7, sort_order=11),
                    OnboardingTask(checklist_id=checklist.id, title="Review Company Safety Manual", category="Safety", due_days=3, sort_order=12),
                ]
                db.add_all(ob_tasks)

                review = PerformanceReview(org_id=org.id, user_id=admin.id, reviewer_id=admin.id,
                    period_start=now - timedelta(days=365), period_end=now - timedelta(days=1),
                    review_date=now - timedelta(days=7), overall_rating="meets_expectations",
                    technical_score=4.2, safety_score=4.5, teamwork_score=4.0, attendance_score=4.8, quality_score=4.3,
                    strengths="Strong technical knowledge of fiber optic systems. Excellent safety record. Reliable attendance.",
                    areas_for_improvement="Could improve delegation skills and documentation of field procedures.",
                    goals="Complete Fujikura certification by Q2. Mentor 2 new technicians. Reduce rework rate by 15%.",
                    status="completed", acknowledged_at=now - timedelta(days=5))
                db.add(review)

                comp = CompensationRecord(org_id=org.id, user_id=admin.id, pay_type="hourly",
                    hourly_rate=42.50, overtime_rate=63.75, per_diem=55.00,
                    effective_date=now - timedelta(days=180), reason="Annual review increase", is_current=True)
                db.add(comp)

                skills_data = [
                    {"skill": "Fiber Splicing (Fusion)", "cat": "Technical", "level": 5, "years": 8, "cert": True},
                    {"skill": "OTDR Testing", "cat": "Technical", "level": 4, "years": 6, "cert": True},
                    {"skill": "Aerial Construction", "cat": "Construction", "level": 4, "years": 7, "cert": False},
                    {"skill": "Underground Boring", "cat": "Construction", "level": 3, "years": 4, "cert": False},
                    {"skill": "Project Management", "cat": "Management", "level": 3, "years": 3, "cert": False},
                    {"skill": "CDL Class B Operation", "cat": "Driving", "level": 5, "years": 10, "cert": True},
                    {"skill": "Bucket Truck Operation", "cat": "Equipment", "level": 4, "years": 6, "cert": True},
                    {"skill": "Confined Space Entry", "cat": "Safety", "level": 3, "years": 4, "cert": True},
                ]
                for sd in skills_data:
                    db.add(SkillEntry(org_id=org.id, user_id=admin.id, skill_name=sd["skill"],
                        category=sd["cat"], proficiency_level=sd["level"],
                        years_experience=sd["years"], certified=sd["cert"]))

                hr_trainings = [
                    HRTrainingRecord(org_id=org.id, user_id=admin.id, training_name="Anti-Harassment Training",
                        training_type="compliance", provider="HR Compliance LLC",
                        completion_date=now - timedelta(days=60), expiry_date=now + timedelta(days=305),
                        status="completed", required=True, hours=2),
                    HRTrainingRecord(org_id=org.id, user_id=admin.id, training_name="Leadership Development Program",
                        training_type="professional", provider="Dale Carnegie",
                        completion_date=now - timedelta(days=120), status="completed", hours=40, cost=1500),
                ]
                db.add_all(hr_trainings)

                db.commit()

    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
    finally:
        db.close()


@app.get("/api/config")
def get_config():
    from app.core.config import MAPBOX_PUBLIC_TOKEN
    return {"mapbox_token": MAPBOX_PUBLIC_TOKEN}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
