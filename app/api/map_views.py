from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import SavedMapView, Project, User
from app.schemas.schemas import SavedMapViewCreate, SavedMapViewResponse

router = APIRouter(prefix="/api", tags=["map_views"])

@router.get("/projects/{project_id}/map-views", response_model=list[SavedMapViewResponse])
def list_map_views(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    views = db.query(SavedMapView).filter(
        SavedMapView.project_id == project_id,
        SavedMapView.user_id == user.id
    ).order_by(SavedMapView.created_at.desc()).all()
    
    return [SavedMapViewResponse(
        id=v.id, project_id=v.project_id, name=v.name,
        center_lng=v.center_lng, center_lat=v.center_lat,
        zoom=v.zoom, bearing=v.bearing, pitch=v.pitch,
        filters=v.filters, layer_visibility=v.layer_visibility,
        is_default=v.is_default, created_at=v.created_at
    ) for v in views]

@router.post("/projects/{project_id}/map-views", response_model=SavedMapViewResponse, status_code=201)
def save_map_view(
    project_id: str,
    data: SavedMapViewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    if data.is_default:
        existing = db.query(SavedMapView).filter(
            SavedMapView.project_id == project_id,
            SavedMapView.user_id == user.id,
            SavedMapView.is_default == True
        ).all()
        for v in existing:
            v.is_default = False
    
    view = SavedMapView(
        project_id=project_id, user_id=user.id,
        name=data.name, center_lng=data.center_lng,
        center_lat=data.center_lat, zoom=data.zoom,
        bearing=data.bearing, pitch=data.pitch,
        filters=data.filters, layer_visibility=data.layer_visibility,
        is_default=data.is_default
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    
    return SavedMapViewResponse(
        id=view.id, project_id=view.project_id, name=view.name,
        center_lng=view.center_lng, center_lat=view.center_lat,
        zoom=view.zoom, bearing=view.bearing, pitch=view.pitch,
        filters=view.filters, layer_visibility=view.layer_visibility,
        is_default=view.is_default, created_at=view.created_at
    )

@router.delete("/map-views/{view_id}", status_code=204)
def delete_map_view(
    view_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    view = db.query(SavedMapView).filter(SavedMapView.id == view_id, SavedMapView.user_id == user.id).first()
    if not view:
        raise HTTPException(status_code=404, detail="Map view not found")
    db.delete(view)
    db.commit()
