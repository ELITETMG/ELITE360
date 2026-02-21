from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import json, csv, io, zipfile, tempfile
from geoalchemy2.functions import ST_AsGeoJSON
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import Task, TaskStatus, Project, User, TaskType, Material, ProjectBudget, Activity

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

STATUS_COLORS = {
    "not_started": "#94A3B8",
    "in_progress": "#3B82F6",
    "submitted": "#F59E0B",
    "approved": "#10B981",
    "billed": "#8B5CF6",
    "rework": "#EF4444",
    "failed_inspection": "#DC2626",
}

PLATFORMS = [
    {
        "id": "vetro",
        "name": "Vetro FiberMap",
        "description": "Export fiber network data to Vetro FiberMap for advanced fiber planning and design",
        "logo_icon": "🗺️",
        "export_formats": ["geojson"],
        "status": "available",
        "features": ["Fiber route export", "Strand mapping", "Cable inventory sync", "Splice point data"]
    },
    {
        "id": "esri",
        "name": "ESRI ArcGIS",
        "description": "Export to ESRI ArcGIS for enterprise GIS analysis and mapping",
        "logo_icon": "🌐",
        "export_formats": ["geojson", "shapefile"],
        "status": "available",
        "features": ["Feature class export", "Attribute mapping", "Spatial analysis", "Web map integration"]
    },
    {
        "id": "threegis",
        "name": "3-GIS",
        "description": "Export to 3-GIS for fiber network management and OSP design",
        "logo_icon": "📡",
        "export_formats": ["geojson"],
        "status": "available",
        "features": ["Network element export", "Lifecycle tracking", "Asset management", "Design integration"]
    },
    {
        "id": "powerbi",
        "name": "Power BI",
        "description": "Export project analytics data for Power BI dashboards and reporting",
        "logo_icon": "📊",
        "export_formats": ["json"],
        "status": "available",
        "features": ["Task analytics", "Status breakdown", "Timeline data", "Budget tracking"]
    },
    {
        "id": "deepup",
        "name": "Deep Up",
        "description": "Export underground infrastructure data for Deep Up subsurface mapping",
        "logo_icon": "⛏️",
        "export_formats": ["geojson"],
        "status": "available",
        "features": ["Underground asset export", "Depth metadata", "Conduit mapping", "Material tracking"]
    },
    {
        "id": "qgis",
        "name": "QGIS",
        "description": "Export standard GeoJSON for use in QGIS desktop GIS application",
        "logo_icon": "🗂️",
        "export_formats": ["geojson"],
        "status": "available",
        "features": ["Standard GeoJSON export", "Full attribute data", "Style metadata", "Layer-ready format"]
    },
    {
        "id": "googleearth",
        "name": "Google Earth",
        "description": "Export KML for visualization in Google Earth Pro and Google Earth Web",
        "logo_icon": "🌍",
        "export_formats": ["kml"],
        "status": "available",
        "features": ["KML export", "Status-based styling", "Placemark data", "3D visualization ready"]
    },
]

PLATFORM_IDS = {p["id"] for p in PLATFORMS}


def _get_project_tasks_with_geometry(project_id: str, user: User, db: Session):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.geometry.isnot(None)
    ).all()
    return project, tasks


def _task_to_geojson_feature(task, db):
    raw = db.execute(ST_AsGeoJSON(task.geometry)).scalar()
    if not raw:
        return None
    geom = json.loads(raw)
    tt_name = task.task_type.name if task.task_type else None
    return geom, tt_name


def _build_vetro_export(project, tasks, db):
    features = []
    for i, t in enumerate(tasks):
        result = _task_to_geojson_feature(t, db)
        if not result:
            continue
        geom, tt_name = result
        tt_category = (tt_name or "").lower()
        fiber_type = "distribution"
        if "trunk" in t.name.lower() or "main" in t.name.lower():
            fiber_type = "feeder"
        elif "drop" in tt_category:
            fiber_type = "drop"
        elif "branch" in t.name.lower():
            fiber_type = "branch"

        placement_type = "aerial"
        if "underground" in tt_category or "conduit" in tt_category:
            placement_type = "underground"

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "vetro_id": f"VTRO-{t.id[:8].upper()}",
                "name": t.name,
                "fiber_type": fiber_type,
                "cable_count": 1,
                "status": t.status.value if t.status else "not_started",
                "strand_count": int(t.planned_qty) if t.planned_qty and t.planned_qty <= 96 else 12,
                "material": tt_name or "fiber",
                "placement_type": placement_type,
                "planned_qty": t.planned_qty,
                "actual_qty": t.actual_qty or 0,
                "unit": t.unit,
            }
        })
    return {
        "type": "FeatureCollection",
        "name": f"vetro_export_{project.name}",
        "features": features
    }


def _build_esri_export(project, tasks, db):
    features = []
    for i, t in enumerate(tasks):
        result = _task_to_geojson_feature(t, db)
        if not result:
            continue
        geom, tt_name = result
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "OBJECTID": i + 1,
                "GlobalID": t.id,
                "SHAPE_Length": t.planned_qty or 0,
                "NAME": t.name,
                "STATUS": (t.status.value if t.status else "not_started").upper(),
                "TASK_TYPE": tt_name or "",
                "PLANNED_QTY": t.planned_qty or 0,
                "ACTUAL_QTY": t.actual_qty or 0,
                "UNIT": t.unit or "",
                "CREATED_DATE": t.created_at.isoformat() if t.created_at else None,
                "UPDATED_DATE": t.updated_at.isoformat() if t.updated_at else None,
            }
        })
    return {
        "type": "FeatureCollection",
        "name": f"esri_export_{project.name}",
        "features": features
    }


def _build_threegis_export(project, tasks, db):
    features = []
    for t in tasks:
        result = _task_to_geojson_feature(t, db)
        if not result:
            continue
        geom, tt_name = result

        status_map = {
            "not_started": "PROPOSED",
            "in_progress": "IN_SERVICE",
            "submitted": "PENDING_REVIEW",
            "approved": "IN_SERVICE",
            "billed": "IN_SERVICE",
            "rework": "MAINTENANCE",
            "failed_inspection": "OUT_OF_SERVICE",
        }
        lifecycle = status_map.get(t.status.value if t.status else "not_started", "PROPOSED")

        feature_class = "FIBER_CABLE"
        if tt_name:
            lower = tt_name.lower()
            if "conduit" in lower:
                feature_class = "CONDUIT"
            elif "splice" in lower:
                feature_class = "SPLICE_CLOSURE"
            elif "handhole" in lower or "vault" in lower:
                feature_class = "STRUCTURE"
            elif "drop" in lower:
                feature_class = "DROP_CABLE"

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "FEATURE_ID": f"3GIS-{t.id[:8].upper()}",
                "NAME": t.name,
                "FEATURE_CLASS": feature_class,
                "OWNERSHIP": "OWNED",
                "LIFECYCLE_STATUS": lifecycle,
                "PLANNED_QTY": t.planned_qty or 0,
                "ACTUAL_QTY": t.actual_qty or 0,
                "UNIT": t.unit or "",
            }
        })
    return {
        "type": "FeatureCollection",
        "name": f"threegis_export_{project.name}",
        "features": features
    }


def _build_powerbi_export(project, tasks, db):
    tasks_table = []
    status_counts = {}
    type_counts = {}
    timeline_data = []

    all_tasks = db.query(Task).filter(Task.project_id == project.id).all()

    for t in all_tasks:
        tt_name = t.task_type.name if t.task_type else "Untyped"
        status_val = t.status.value if t.status else "not_started"

        tasks_table.append({
            "id": t.id,
            "name": t.name,
            "status": status_val,
            "task_type": tt_name,
            "planned_qty": t.planned_qty or 0,
            "actual_qty": t.actual_qty or 0,
            "unit": t.unit or "",
            "progress_pct": round(((t.actual_qty or 0) / t.planned_qty * 100)) if t.planned_qty else 0,
            "unit_cost": t.unit_cost or 0,
            "total_cost": t.total_cost or 0,
            "actual_cost": t.actual_cost or 0,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        })

        status_counts[status_val] = status_counts.get(status_val, 0) + 1
        type_counts[tt_name] = type_counts.get(tt_name, 0) + 1

        if t.created_at:
            timeline_data.append({
                "date": t.created_at.strftime("%Y-%m-%d"),
                "task_id": t.id,
                "event": "created",
                "status": status_val,
            })

    total_tasks = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.status and t.status.value in ("approved", "billed"))
    total_planned = sum(t.planned_qty or 0 for t in all_tasks)
    total_actual = sum(t.actual_qty or 0 for t in all_tasks)

    return {
        "tasks_table": tasks_table,
        "summary_stats": {
            "total_tasks": total_tasks,
            "completed_tasks": completed,
            "completion_pct": round((completed / total_tasks * 100)) if total_tasks else 0,
            "total_planned_qty": total_planned,
            "total_actual_qty": total_actual,
            "overall_progress_pct": round((total_actual / total_planned * 100)) if total_planned else 0,
        },
        "status_breakdown": [{"status": k, "count": v} for k, v in status_counts.items()],
        "type_breakdown": [{"task_type": k, "count": v} for k, v in type_counts.items()],
        "timeline_data": timeline_data,
    }


def _build_deepup_export(project, tasks, db):
    underground_keywords = ["underground", "conduit", "buried"]
    features = []
    for t in tasks:
        tt_name = t.task_type.name if t.task_type else ""
        lower_name = tt_name.lower()
        is_underground = any(kw in lower_name for kw in underground_keywords)
        if not is_underground:
            continue

        result = _task_to_geojson_feature(t, db)
        if not result:
            continue
        geom, _ = result

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "deepup_id": f"DU-{t.id[:8].upper()}",
                "name": t.name,
                "asset_type": "conduit" if "conduit" in lower_name else "buried_cable",
                "depth_meters": 1.2,
                "material": tt_name,
                "status": t.status.value if t.status else "not_started",
                "planned_qty": t.planned_qty or 0,
                "actual_qty": t.actual_qty or 0,
                "unit": t.unit or "",
                "installation_method": "trenching" if "conduit" in lower_name else "directional_boring",
            }
        })
    return {
        "type": "FeatureCollection",
        "name": f"deepup_export_{project.name}",
        "features": features
    }


def _build_qgis_export(project, tasks, db):
    features = []
    for t in tasks:
        result = _task_to_geojson_feature(t, db)
        if not result:
            continue
        geom, tt_name = result
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "status": t.status.value if t.status else "not_started",
                "task_type": tt_name,
                "planned_qty": t.planned_qty,
                "actual_qty": t.actual_qty or 0,
                "unit": t.unit,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
        })
    return {
        "type": "FeatureCollection",
        "name": f"qgis_export_{project.name}",
        "features": features
    }


def _coords_to_kml_string(geom):
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    if geom_type == "Point":
        return f"<Point><coordinates>{coords[0]},{coords[1]},0</coordinates></Point>"
    elif geom_type == "LineString":
        coord_str = " ".join(f"{c[0]},{c[1]},0" for c in coords)
        return f"<LineString><coordinates>{coord_str}</coordinates></LineString>"
    elif geom_type == "Polygon":
        rings_kml = ""
        for i, ring in enumerate(coords):
            coord_str = " ".join(f"{c[0]},{c[1]},0" for c in ring)
            if i == 0:
                rings_kml += f"<outerBoundaryIs><LinearRing><coordinates>{coord_str}</coordinates></LinearRing></outerBoundaryIs>"
            else:
                rings_kml += f"<innerBoundaryIs><LinearRing><coordinates>{coord_str}</coordinates></LinearRing></innerBoundaryIs>"
        return f"<Polygon>{rings_kml}</Polygon>"
    return ""


def _build_kml_export(project, tasks, db):
    kml_styles = ""
    for status, color in STATUS_COLORS.items():
        hex_color = color.lstrip("#")
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        kml_color = f"ff{b}{g}{r}"
        kml_styles += f"""<Style id="style_{status}">
    <IconStyle><color>{kml_color}</color><scale>1.0</scale></IconStyle>
    <LineStyle><color>{kml_color}</color><width>3</width></LineStyle>
    <PolyStyle><color>80{b}{g}{r}</color></PolyStyle>
  </Style>\n  """

    placemarks = ""
    for t in tasks:
        result = _task_to_geojson_feature(t, db)
        if not result:
            continue
        geom, tt_name = result
        status_val = t.status.value if t.status else "not_started"
        geom_kml = _coords_to_kml_string(geom)

        extended_data = f"""<ExtendedData>
        <Data name="id"><value>{t.id}</value></Data>
        <Data name="status"><value>{status_val}</value></Data>
        <Data name="task_type"><value>{tt_name or ''}</value></Data>
        <Data name="planned_qty"><value>{t.planned_qty or 0}</value></Data>
        <Data name="actual_qty"><value>{t.actual_qty or 0}</value></Data>
        <Data name="unit"><value>{t.unit or ''}</value></Data>
      </ExtendedData>"""

        placemarks += f"""<Placemark>
      <name>{t.name}</name>
      <description>{t.description or ''}</description>
      <styleUrl>#style_{status_val}</styleUrl>
      {extended_data}
      {geom_kml}
    </Placemark>\n    """

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{project.name}</name>
    <description>{project.description or ''}</description>
  {kml_styles}
  {placemarks}
  </Document>
</kml>"""
    return kml


PLATFORM_CONFIGS = {
    "vetro": {
        "platform": "vetro",
        "name": "Vetro FiberMap",
        "connection_fields": [
            {"field": "api_url", "label": "Vetro API URL", "type": "url", "required": True, "placeholder": "https://api.vetrofibermap.com/v2"},
            {"field": "api_key", "label": "API Key", "type": "secret", "required": True, "placeholder": "Enter your Vetro API key"},
            {"field": "project_id", "label": "Vetro Project ID", "type": "text", "required": True, "placeholder": "Project identifier in Vetro"},
        ],
        "webhook_url": None,
        "documentation_url": "https://docs.vetrofibermap.com/api",
    },
    "esri": {
        "platform": "esri",
        "name": "ESRI ArcGIS",
        "connection_fields": [
            {"field": "portal_url", "label": "ArcGIS Portal URL", "type": "url", "required": True, "placeholder": "https://www.arcgis.com"},
            {"field": "username", "label": "ArcGIS Username", "type": "text", "required": True, "placeholder": "Enter your ArcGIS username"},
            {"field": "password", "label": "ArcGIS Password", "type": "secret", "required": True, "placeholder": "Enter your ArcGIS password"},
            {"field": "feature_service_url", "label": "Feature Service URL", "type": "url", "required": False, "placeholder": "Optional: Target feature service URL"},
        ],
        "webhook_url": None,
        "documentation_url": "https://developers.arcgis.com/rest/",
    },
    "threegis": {
        "platform": "threegis",
        "name": "3-GIS",
        "connection_fields": [
            {"field": "server_url", "label": "3-GIS Server URL", "type": "url", "required": True, "placeholder": "https://your-3gis-server.com"},
            {"field": "api_token", "label": "API Token", "type": "secret", "required": True, "placeholder": "Enter your 3-GIS API token"},
            {"field": "workspace", "label": "Workspace Name", "type": "text", "required": True, "placeholder": "Target workspace in 3-GIS"},
        ],
        "webhook_url": None,
        "documentation_url": "https://docs.3-gis.com/api",
    },
    "powerbi": {
        "platform": "powerbi",
        "name": "Power BI",
        "connection_fields": [
            {"field": "workspace_id", "label": "Power BI Workspace ID", "type": "text", "required": True, "placeholder": "Power BI workspace GUID"},
            {"field": "dataset_id", "label": "Dataset ID", "type": "text", "required": False, "placeholder": "Optional: Target dataset ID"},
            {"field": "client_id", "label": "Azure AD Client ID", "type": "text", "required": True, "placeholder": "Azure AD application client ID"},
            {"field": "client_secret", "label": "Azure AD Client Secret", "type": "secret", "required": True, "placeholder": "Azure AD application client secret"},
        ],
        "webhook_url": None,
        "documentation_url": "https://learn.microsoft.com/en-us/power-bi/developer/",
    },
    "deepup": {
        "platform": "deepup",
        "name": "Deep Up",
        "connection_fields": [
            {"field": "api_url", "label": "Deep Up API URL", "type": "url", "required": True, "placeholder": "https://api.deepup.com/v1"},
            {"field": "api_key", "label": "API Key", "type": "secret", "required": True, "placeholder": "Enter your Deep Up API key"},
            {"field": "project_name", "label": "Project Name", "type": "text", "required": False, "placeholder": "Optional: Project name in Deep Up"},
        ],
        "webhook_url": None,
        "documentation_url": "https://docs.deepup.com",
    },
    "qgis": {
        "platform": "qgis",
        "name": "QGIS",
        "connection_fields": [
            {"field": "export_path", "label": "Export Directory", "type": "text", "required": False, "placeholder": "Local directory path for exports"},
        ],
        "webhook_url": None,
        "documentation_url": "https://docs.qgis.org",
    },
    "googleearth": {
        "platform": "googleearth",
        "name": "Google Earth",
        "connection_fields": [
            {"field": "export_path", "label": "Export Directory", "type": "text", "required": False, "placeholder": "Local directory path for KML exports"},
        ],
        "webhook_url": None,
        "documentation_url": "https://developers.google.com/kml/documentation",
    },
}


@router.get("/platforms")
def list_platforms(user: User = Depends(get_current_user)):
    return {"platforms": PLATFORMS}


@router.get("/{platform}/export")
def export_platform_data(
    platform: str,
    project_id: str = Query(..., description="Project ID to export"),
    format: str = Query(None, description="Export format override"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if platform not in PLATFORM_IDS:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not supported. Available: {', '.join(sorted(PLATFORM_IDS))}")

    project, tasks = _get_project_tasks_with_geometry(project_id, user, db)

    if platform == "vetro":
        data = _build_vetro_export(project, tasks, db)
        return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=vetro_export_{project.id[:8]}.geojson"})

    elif platform == "esri":
        data = _build_esri_export(project, tasks, db)
        return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=esri_export_{project.id[:8]}.geojson"})

    elif platform == "threegis":
        data = _build_threegis_export(project, tasks, db)
        return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=threegis_export_{project.id[:8]}.geojson"})

    elif platform == "powerbi":
        data = _build_powerbi_export(project, tasks, db)
        return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=powerbi_export_{project.id[:8]}.json"})

    elif platform == "deepup":
        data = _build_deepup_export(project, tasks, db)
        return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=deepup_export_{project.id[:8]}.geojson"})

    elif platform == "qgis":
        data = _build_qgis_export(project, tasks, db)
        return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=qgis_export_{project.id[:8]}.geojson"})

    elif platform == "googleearth":
        kml_content = _build_kml_export(project, tasks, db)
        return StreamingResponse(
            io.BytesIO(kml_content.encode("utf-8")),
            media_type="application/vnd.google-earth.kml+xml",
            headers={"Content-Disposition": f"attachment; filename=export_{project.id[:8]}.kml"}
        )


@router.get("/{platform}/config")
def get_platform_config(
    platform: str,
    user: User = Depends(get_current_user)
):
    if platform not in PLATFORM_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Platform '{platform}' not supported. Available: {', '.join(sorted(PLATFORM_CONFIGS.keys()))}")
    return PLATFORM_CONFIGS[platform]


@router.post("/webhook-test")
def webhook_test(user: User = Depends(get_current_user)):
    return {
        "status": "success",
        "message": "Webhook connection test successful",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "user": user.full_name,
    }
