import json
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON, ST_MakeEnvelope, ST_Intersects
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import Task, TaskStatus, Project, User, AuditLog, FieldEntry, TaskType, ImportBatch, Activity
from app.schemas.schemas import (
    TaskCreate, TaskUpdate, TaskResponse,
    FieldEntryCreate, FieldEntryResponse,
    ImportResult, ImportError as ImportErrorSchema,
    BulkTaskUpdate, ImportBatchResponse
)
from app.services.import_service import detect_format, parse_file

router = APIRouter(prefix="/api", tags=["tasks"])

VALID_TASK_STATUSES = [s.value for s in TaskStatus]


def _get_project_or_404(project_id: str, user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    return project


def task_to_response(task, db) -> TaskResponse:
    geojson = None
    if task.geometry is not None:
        raw = db.execute(ST_AsGeoJSON(task.geometry)).scalar()
        if raw:
            geojson = json.loads(raw)
    tt_name = task.task_type.name if task.task_type else None
    tt_color = task.task_type.color if task.task_type else None
    assigned_name = task.assigned_user.full_name if task.assigned_to and hasattr(task, 'assigned_user') and task.assigned_user else None
    return TaskResponse(
        id=task.id, name=task.name, description=task.description,
        project_id=task.project_id, work_package_id=task.work_package_id,
        task_type_id=task.task_type_id, task_type_name=tt_name,
        task_type_color=tt_color, status=task.status.value,
        planned_qty=task.planned_qty, actual_qty=task.actual_qty,
        unit=task.unit, geometry_geojson=geojson,
        unit_cost=task.unit_cost,
        total_cost=task.total_cost,
        actual_cost=task.actual_cost,
        assigned_to=task.assigned_to,
        assigned_user_name=assigned_name,
        priority=task.priority,
        due_date=task.due_date,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at, updated_at=task.updated_at
    )


@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
def list_tasks(
    project_id: str,
    status: str = Query(None),
    task_type_id: str = Query(None),
    work_package_id: str = Query(None),
    bbox: str = Query(None, description="minlon,minlat,maxlon,maxlat"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_project_or_404(project_id, user, db)
    q = db.query(Task).filter(Task.project_id == project_id)
    if status:
        if status in VALID_TASK_STATUSES:
            q = q.filter(Task.status == status)
    if task_type_id:
        q = q.filter(Task.task_type_id == task_type_id)
    if work_package_id:
        q = q.filter(Task.work_package_id == work_package_id)
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            envelope = ST_MakeEnvelope(parts[0], parts[1], parts[2], parts[3], 4326)
            q = q.filter(ST_Intersects(Task.geometry, envelope))
        except (ValueError, IndexError):
            pass

    tasks = q.order_by(Task.created_at.desc()).all()
    return [task_to_response(t, db) for t in tasks]


STATUS_COLORS = {
    "not_started": "#94A3B8",
    "in_progress": "#3B82F6",
    "submitted": "#F59E0B",
    "approved": "#10B981",
    "billed": "#8B5CF6",
    "rework": "#EF4444",
    "failed_inspection": "#DC2626",
}

CATEGORY_MAP = {
    "Aerial Fiber": "span",
    "Underground Conduit": "span",
    "Branch fiber": "span",
    "Drop Installation": "drop",
    "Splice Point": "node",
    "Handhole/Vault": "node",
}


def _classify_feature(task):
    tt_name = task.task_type.name if task.task_type else ""
    for key, cat in CATEGORY_MAP.items():
        if key.lower() in tt_name.lower():
            return cat
    geom_type = None
    if task.geometry is not None:
        from sqlalchemy import func as sqlfunc
        pass
    return "other"


@router.get("/projects/{project_id}/map-layer")
def get_map_layer(
    project_id: str,
    bbox: str = Query(None),
    status: str = Query(None),
    task_type_id: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_project_or_404(project_id, user, db)
    q = db.query(Task).filter(
        Task.project_id == project_id,
        Task.geometry.isnot(None)
    )
    if status and status in VALID_TASK_STATUSES:
        q = q.filter(Task.status == status)
    if task_type_id:
        q = q.filter(Task.task_type_id == task_type_id)
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            envelope = ST_MakeEnvelope(parts[0], parts[1], parts[2], parts[3], 4326)
            q = q.filter(ST_Intersects(Task.geometry, envelope))
        except (ValueError, IndexError):
            pass

    tasks = q.all()
    features = []
    for t in tasks:
        raw = db.execute(ST_AsGeoJSON(t.geometry)).scalar()
        if raw:
            geom = json.loads(raw)
            tt_name = t.task_type.name if t.task_type else None
            tt_color = t.task_type.color if t.task_type else "#3B82F6"
            status_val = t.status.value
            status_color = STATUS_COLORS.get(status_val, "#94A3B8")

            cat = "other"
            for key, c in CATEGORY_MAP.items():
                if tt_name and key.lower() in tt_name.lower():
                    cat = c
                    break
            if cat == "other":
                if geom["type"] == "LineString" or geom["type"] == "MultiLineString":
                    cat = "span"
                elif geom["type"] == "Polygon" or geom["type"] == "MultiPolygon":
                    cat = "zone"
                elif geom["type"] == "Point":
                    cat = "node"

            remaining = (t.planned_qty or 0) - (t.actual_qty or 0)
            pct = round(((t.actual_qty or 0) / t.planned_qty * 100)) if t.planned_qty else 0

            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "status": status_val,
                    "status_color": status_color,
                    "task_type": tt_name,
                    "task_type_color": tt_color,
                    "category": cat,
                    "planned_qty": t.planned_qty,
                    "actual_qty": t.actual_qty or 0,
                    "remaining_qty": remaining,
                    "progress_pct": pct,
                    "unit": t.unit,
                    "work_package_id": t.work_package_id,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                    "style_color": t.style_color,
                    "style_width": t.style_width,
                    "style_opacity": t.style_opacity,
                    "style_icon": t.style_icon,
                }
            })
    return {"type": "FeatureCollection", "features": features}


@router.get("/tasks/import-template")
def download_import_template(user: User = Depends(get_current_user)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "description", "task_type", "planned_qty", "unit", "status", "longitude", "latitude", "geometry_wkt"])
    writer.writerow(["Sample Span 1", "Aerial fiber run", "Aerial Fiber", "500", "feet", "not_started", "-97.7431", "30.2672", ""])
    writer.writerow(["Sample Node 1", "Splice point", "Splice Point", "1", "each", "not_started", "-97.7420", "30.2680", ""])
    writer.writerow(["Sample Line", "Underground conduit", "Underground Conduit", "200", "feet", "not_started", "", "", "LINESTRING(-97.7431 30.2672, -97.7420 30.2680)"])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=task_import_template.csv"}
    )


@router.post("/tasks", response_model=TaskResponse)
def create_task(
    data: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_project_or_404(data.project_id, user, db)
    task = Task(
        name=data.name, description=data.description,
        project_id=data.project_id, work_package_id=data.work_package_id,
        task_type_id=data.task_type_id, planned_qty=data.planned_qty,
        unit=data.unit
    )
    if data.geometry_geojson:
        task.geometry = ST_GeomFromGeoJSON(json.dumps(data.geometry_geojson))

    db.add(task)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="task", entity_id=task.id))
    db.commit()
    db.refresh(task)
    return task_to_response(task, db)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _get_project_or_404(task.project_id, user, db)
    return task_to_response(task, db)


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str, data: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _get_project_or_404(task.project_id, user, db)

    if data.name is not None:
        task.name = data.name
    if data.description is not None:
        task.description = data.description
    if data.status is not None:
        if data.status not in VALID_TASK_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_TASK_STATUSES}")
        task.status = data.status
    if data.planned_qty is not None:
        task.planned_qty = data.planned_qty
    if data.actual_qty is not None:
        task.actual_qty = data.actual_qty
    if data.work_package_id is not None:
        task.work_package_id = data.work_package_id
    if data.task_type_id is not None:
        task.task_type_id = data.task_type_id
    if data.geometry_geojson is not None:
        task.geometry = ST_GeomFromGeoJSON(json.dumps(data.geometry_geojson))

    db.add(AuditLog(user_id=user.id, action="update", entity_type="task", entity_id=task.id,
                    details=f"status={data.status}" if data.status else None))
    db.commit()
    db.refresh(task)
    return task_to_response(task, db)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _get_project_or_404(task.project_id, user, db)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="task", entity_id=task.id))
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/field-entries", response_model=FieldEntryResponse)
def create_field_entry(
    task_id: str, data: FieldEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _get_project_or_404(task.project_id, user, db)

    if data.offline_client_id:
        existing = db.query(FieldEntry).filter(FieldEntry.offline_client_id == data.offline_client_id).first()
        if existing:
            return FieldEntryResponse(
                id=existing.id, task_id=existing.task_id, user_id=existing.user_id,
                qty_delta=existing.qty_delta, labor_hours=existing.labor_hours,
                notes=existing.notes, created_at=existing.created_at
            )

    entry = FieldEntry(
        task_id=task_id, user_id=user.id,
        qty_delta=data.qty_delta, labor_hours=data.labor_hours,
        notes=data.notes, gps_lat=data.gps_lat, gps_lon=data.gps_lon,
        gps_accuracy=data.gps_accuracy, offline_client_id=data.offline_client_id
    )
    db.add(entry)

    if data.qty_delta:
        task.actual_qty = (task.actual_qty or 0) + data.qty_delta

    deviation_flags = []
    deviation_details = {}

    if data.gps_lat is not None and data.gps_lon is not None and task.geometry is not None:
        try:
            from geoalchemy2.functions import ST_Distance, ST_GeomFromText, ST_Transform
            from sqlalchemy import text as sa_text
            point_wkt = f"POINT({data.gps_lon} {data.gps_lat})"
            dist_query = sa_text(
                "SELECT ST_Distance("
                "ST_Transform(ST_SetSRID(ST_GeomFromText(:point), 4326), 3857), "
                "ST_Transform(:geom::geometry, 3857)"
                ")"
            )
            distance_m = db.execute(dist_query, {"point": point_wkt, "geom": task.geometry}).scalar()
            if distance_m is not None and distance_m > 100:
                deviation_flags.append("gps_distance_exceeded")
                deviation_details["gps_distance_ft"] = round(distance_m * 3.28084)
        except Exception:
            pass

    new_actual = task.actual_qty or 0
    if task.planned_qty and task.planned_qty > 0 and new_actual > task.planned_qty * 1.1:
        pct_over = round(((new_actual - task.planned_qty) / task.planned_qty) * 100)
        deviation_flags.append("qty_threshold_exceeded")
        deviation_details["qty_pct_over"] = pct_over

    if deviation_flags:
        entry.deviation_flags = json.dumps(deviation_flags)
        entry.deviation_details = json.dumps(deviation_details)

    db.add(AuditLog(user_id=user.id, action="field_entry", entity_type="task", entity_id=task_id,
                    details=f"qty_delta={data.qty_delta}"))
    db.commit()
    db.refresh(entry)
    return FieldEntryResponse(
        id=entry.id, task_id=entry.task_id, user_id=entry.user_id,
        qty_delta=entry.qty_delta, labor_hours=entry.labor_hours,
        notes=entry.notes, deviation_flags=entry.deviation_flags,
        deviation_details=entry.deviation_details, created_at=entry.created_at
    )


@router.get("/tasks/{task_id}/field-entries", response_model=list[FieldEntryResponse])
def list_field_entries(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _get_project_or_404(task.project_id, user, db)
    entries = db.query(FieldEntry).filter(FieldEntry.task_id == task_id).order_by(FieldEntry.created_at.desc()).all()
    return [FieldEntryResponse(
        id=e.id, task_id=e.task_id, user_id=e.user_id,
        qty_delta=e.qty_delta, labor_hours=e.labor_hours,
        notes=e.notes, deviation_flags=e.deviation_flags,
        deviation_details=e.deviation_details, created_at=e.created_at
    ) for e in entries]


def _parse_wkt_to_geojson(wkt_str: str) -> dict | None:
    wkt_str = wkt_str.strip()
    upper = wkt_str.upper()
    if upper.startswith("POINT"):
        coords_str = wkt_str[wkt_str.index("(") + 1:wkt_str.rindex(")")].strip()
        parts = coords_str.split()
        return {"type": "Point", "coordinates": [float(parts[0]), float(parts[1])]}
    elif upper.startswith("LINESTRING"):
        coords_str = wkt_str[wkt_str.index("(") + 1:wkt_str.rindex(")")].strip()
        coords = []
        for pair in coords_str.split(","):
            parts = pair.strip().split()
            coords.append([float(parts[0]), float(parts[1])])
        return {"type": "LineString", "coordinates": coords}
    elif upper.startswith("POLYGON"):
        inner = wkt_str[wkt_str.index("((") + 2:wkt_str.rindex("))")]
        rings = []
        for ring_str in inner.split("),("):
            ring = []
            for pair in ring_str.strip().split(","):
                parts = pair.strip().split()
                ring.append([float(parts[0]), float(parts[1])])
            rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}
    return None


def _resolve_task_type(name: str, db: Session) -> str | None:
    if not name:
        return None
    tt = db.query(TaskType).filter(func.lower(TaskType.name) == name.lower().strip()).first()
    return tt.id if tt else None


@router.post("/projects/{project_id}/tasks/import", response_model=ImportResult)
async def import_tasks(
    project_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = _get_project_or_404(project_id, user, db)

    content = await file.read()
    filename = file.filename or ""

    MAX_FILE_SIZE = 10 * 1024 * 1024
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

    file_format = detect_format(filename)
    if file_format == 'unknown':
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Supported: CSV, GeoJSON, KML, KMZ, Shapefile (ZIP), DXF"
        )

    try:
        features, format_name = parse_file(content, file_format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    MAX_ROWS = 5000
    if len(features) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"Import exceeds maximum feature limit of {MAX_ROWS}")

    imported = 0
    errors = []

    for i, feature in enumerate(features):
        row_num = i + 1
        try:
            props = feature.get('properties', {}) or {}
            name = feature.get('name') or props.get('name') or props.get('Name') or props.get('NAME') or f"Imported Feature {row_num}"
            description = feature.get('description') or props.get('description') or props.get('Description') or props.get('desc') or None
            geometry = feature.get('geometry')

            task_type_name = props.get('task_type') or None
            task_type_id = None
            if task_type_name:
                task_type_id = _resolve_task_type(task_type_name, db)
                if task_type_id is None:
                    errors.append(ImportErrorSchema(row=row_num, message=f"Task type '{task_type_name}' not found"))
                    continue

            planned_qty = None
            for key in ["planned_qty", "quantity", "qty", "Quantity"]:
                if key in props and props[key] is not None:
                    try:
                        planned_qty = float(props[key])
                    except (ValueError, TypeError):
                        pass
                    break

            unit_val = props.get("unit") or props.get("Unit") or None

            status_val = props.get("status") or props.get("Status") or "not_started"
            if status_val not in VALID_TASK_STATUSES:
                status_val = "not_started"

            task = Task(
                name=str(name)[:255],
                description=str(description) if description else None,
                project_id=project_id,
                task_type_id=task_type_id,
                planned_qty=planned_qty,
                unit=unit_val,
                status=status_val,
                style_color=feature.get('style_color'),
                style_width=feature.get('style_width'),
                style_opacity=feature.get('style_opacity'),
                style_icon=feature.get('style_icon'),
            )

            if geometry:
                task.geometry = ST_GeomFromGeoJSON(json.dumps(geometry))

            db.add(task)
            db.add(AuditLog(user_id=user.id, action="import_create", entity_type="task", entity_id=task.id))
            imported += 1
        except Exception as e:
            errors.append(ImportErrorSchema(row=row_num, message=str(e)))

    error_details = json.dumps([{"row": e.row, "message": e.message} for e in errors]) if errors else None
    batch = ImportBatch(
        project_id=project_id,
        user_id=user.id,
        filename=filename,
        file_format=format_name,
        total_features=len(features),
        imported_count=imported,
        error_count=len(errors),
        errors=error_details,
        status="completed" if imported > 0 else ("failed" if errors else "completed")
    )
    db.add(batch)

    if imported > 0:
        db.add(Activity(
            project_id=project_id,
            user_id=user.id,
            action="import",
            entity_type="task",
            entity_id=batch.id,
            entity_name=filename,
            details=f"Imported {imported} tasks from {format_name} file '{filename}'"
        ))

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during import: {str(e)}")

    return ImportResult(imported=imported, errors=errors)


@router.get("/projects/{project_id}/import-history", response_model=list[ImportBatchResponse])
def get_import_history(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_project_or_404(project_id, user, db)
    batches = db.query(ImportBatch).filter(
        ImportBatch.project_id == project_id
    ).order_by(ImportBatch.created_at.desc()).all()
    return [ImportBatchResponse(
        id=b.id, project_id=b.project_id, filename=b.filename,
        file_format=b.file_format, total_features=b.total_features,
        imported_count=b.imported_count, error_count=b.error_count,
        errors=b.errors, status=b.status, created_at=b.created_at
    ) for b in batches]


@router.put("/projects/{project_id}/tasks/bulk-update")
def bulk_update_tasks(
    project_id: str,
    data: BulkTaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _get_project_or_404(project_id, user, db)

    if not data.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")

    if data.status and data.status not in VALID_TASK_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_TASK_STATUSES}")

    tasks = db.query(Task).filter(
        Task.id.in_(data.task_ids),
        Task.project_id == project_id
    ).all()
    
    found_ids = {task.id for task in tasks}
    missing_ids = set(data.task_ids) - found_ids
    
    if missing_ids:
        raise HTTPException(status_code=400, detail=f"Task IDs not found in this project: {', '.join(missing_ids)} (error count: {len(missing_ids)})")

    updated = 0
    for task in tasks:
        if data.status:
            task.status = data.status
        if data.work_package_id is not None:
            task.work_package_id = data.work_package_id
        db.add(AuditLog(
            user_id=user.id, action="bulk_update", entity_type="task",
            entity_id=task.id,
            details=f"status={data.status}" if data.status else f"work_package_id={data.work_package_id}"
        ))
        updated += 1

    db.commit()
    return {"updated": updated}


@router.get("/projects/{project_id}/import-history", response_model=list[ImportBatchResponse])
def get_import_history(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = _get_project_or_404(project_id, user, db)
    batches = db.query(ImportBatch).filter(
        ImportBatch.project_id == project_id
    ).order_by(ImportBatch.created_at.desc()).limit(20).all()
    return [
        ImportBatchResponse(
            id=b.id, project_id=b.project_id, filename=b.filename,
            file_format=b.file_format, total_features=b.total_features,
            imported_count=b.imported_count, error_count=b.error_count,
            status=b.status, created_at=b.created_at
        ) for b in batches
    ]
