from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithRole(UserResponse):
    role: Optional[str] = None
    org_id: Optional[str] = None


class OrgCreate(BaseModel):
    name: str
    org_type: str = "contractor"


class OrgResponse(BaseModel):
    id: str
    name: str
    org_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrgMemberCreate(BaseModel):
    user_id: str
    role: str = "crew_member"


class OrgMemberResponse(BaseModel):
    id: str
    org_id: str
    user_id: str
    role: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    executing_org_id: str
    owner_org_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: str
    executing_org_id: str
    owner_org_id: Optional[str]
    executing_org_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    task_count: Optional[int] = 0
    completed_count: Optional[int] = 0

    class Config:
        from_attributes = True


class WorkPackageCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: str


class WorkPackageResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    unit: str = "feet"
    color: Optional[str] = "#3B82F6"


class TaskTypeResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    unit: str
    color: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: str
    work_package_id: Optional[str] = None
    task_type_id: Optional[str] = None
    planned_qty: Optional[float] = None
    unit: Optional[str] = None
    geometry_geojson: Optional[dict] = None
    unit_cost: Optional[float] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    planned_qty: Optional[float] = None
    actual_qty: Optional[float] = None
    work_package_id: Optional[str] = None
    task_type_id: Optional[str] = None
    geometry_geojson: Optional[dict] = None
    unit_cost: Optional[float] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    project_id: str
    work_package_id: Optional[str]
    task_type_id: Optional[str]
    task_type_name: Optional[str] = None
    task_type_color: Optional[str] = None
    status: str
    planned_qty: Optional[float]
    actual_qty: Optional[float]
    unit: Optional[str]
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    assigned_to: Optional[str] = None
    assigned_user_name: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    geometry_geojson: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FieldEntryCreate(BaseModel):
    task_id: str
    qty_delta: Optional[float] = None
    labor_hours: Optional[float] = None
    notes: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy: Optional[float] = None
    offline_client_id: Optional[str] = None


class FieldEntryResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    qty_delta: Optional[float]
    labor_hours: Optional[float]
    notes: Optional[str]
    deviation_flags: Optional[str] = None
    deviation_details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ImportError(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    imported: int
    errors: list[ImportError]


class AttachmentResponse(BaseModel):
    id: str
    filename: str
    file_path: str
    file_type: Optional[str]
    file_size: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class InspectionTemplateCreate(BaseModel):
    name: str
    task_type_id: Optional[str] = None
    checklist_items: Optional[str] = None
    require_photos: bool = True


class InspectionTemplateResponse(BaseModel):
    id: str
    name: str
    task_type_id: Optional[str]
    checklist_items: Optional[str]
    require_photos: bool
    created_at: datetime

    class Config:
        from_attributes = True


class InspectionCreate(BaseModel):
    template_id: Optional[str] = None
    comments: Optional[str] = None


class InspectionUpdate(BaseModel):
    checklist_results: Optional[str] = None
    comments: Optional[str] = None
    status: Optional[str] = None


class InspectionResponse(BaseModel):
    id: str
    task_id: str
    template_id: Optional[str]
    inspector_id: str
    inspector_name: Optional[str] = None
    status: str
    checklist_results: Optional[str]
    comments: Optional[str]
    template_name: Optional[str] = None
    checklist_items: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BulkTaskUpdate(BaseModel):
    task_ids: list[str]
    status: Optional[str] = None
    work_package_id: Optional[str] = None


class DashboardStats(BaseModel):
    total_projects: int
    active_projects: int
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    total_planned_qty: float
    total_actual_qty: float


class ImportBatchResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_format: str
    total_features: int
    imported_count: int
    error_count: int
    errors: Optional[str] = None
    status: str
    created_at: datetime


class MaterialCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit: str = "each"
    unit_cost: Optional[float] = None
    stock_qty: float = 0
    min_stock_qty: float = 0
    description: Optional[str] = None


class MaterialResponse(BaseModel):
    id: str
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit: str
    unit_cost: Optional[float] = None
    stock_qty: float
    min_stock_qty: float
    description: Optional[str] = None
    created_at: datetime


class TaskMaterialCreate(BaseModel):
    material_id: str
    planned_qty: float = 0


class TaskMaterialResponse(BaseModel):
    id: str
    task_id: str
    material_id: str
    material_name: Optional[str] = None
    material_sku: Optional[str] = None
    planned_qty: float
    actual_qty: float
    created_at: datetime


class ActivityResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime


class ProjectBudgetCreate(BaseModel):
    total_budget: float = 0
    labor_budget: float = 0
    material_budget: float = 0
    contingency_pct: float = 10.0
    currency: str = "USD"


class ProjectBudgetResponse(BaseModel):
    id: str
    project_id: str
    total_budget: float
    labor_budget: float
    material_budget: float
    contingency_pct: float
    currency: str
    spent_to_date: Optional[float] = None
    remaining: Optional[float] = None
    created_at: datetime


class DocumentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    current_version: int
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_by: str
    uploader_name: Optional[str] = None
    locked_by: Optional[str] = None
    locker_name: Optional[str] = None
    locked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version_number: int
    file_size: Optional[int] = None
    change_notes: Optional[str] = None
    uploaded_by: str
    uploader_name: Optional[str] = None
    created_at: datetime


class SavedMapViewCreate(BaseModel):
    name: str
    center_lng: float
    center_lat: float
    zoom: float
    bearing: float = 0
    pitch: float = 0
    filters: Optional[str] = None
    layer_visibility: Optional[str] = None
    is_default: bool = False


class SavedMapViewResponse(BaseModel):
    id: str
    project_id: str
    name: str
    center_lng: float
    center_lat: float
    zoom: float
    bearing: float
    pitch: float
    filters: Optional[str] = None
    layer_visibility: Optional[str] = None
    is_default: bool
    created_at: datetime
