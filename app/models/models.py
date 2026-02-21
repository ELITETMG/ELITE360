import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey,
    Enum as SAEnum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.models.base import Base
import enum

__all__ = [
    "Org", "OrgType", "User", "OrgMember", "Project", "ProjectStatus",
    "WorkPackage", "TaskType", "Task", "TaskStatus", "FieldEntry",
    "Attachment", "AuditLog", "RoleName", "InspectionStatus",
    "InspectionTemplate", "Inspection", "ImportBatch", "ProjectBudget",
    "Material", "TaskMaterial", "Activity", "Document", "DocumentVersion",
    "SavedMapView", "UserProfile", "OrgInvite", "InvoiceStatus",
    "Invoice", "InvoiceLineItem", "RateCard", "Payment", "ChangeOrder",
    "Crew", "CrewMember", "DispatchJob", "DispatchJobStatus",
    "AssetStatus", "AssetCategory", "Asset", "AssetAllocation",
    "AssetIncident", "AssetMaintenance", "FleetVehicle", "FleetVehicleStatus",
    "FleetTelemetry", "TechnicianLocation", "TelematicsIntegration",
    "SafetyIncidentStatus", "SafetyIncidentSeverity", "SafetyIncident",
    "SafetyInspectionTemplate", "SafetyInspectionRecord",
    "ToolboxTalk", "ToolboxTalkAttendance",
    "SafetyTraining", "PPECompliance", "CorrectiveAction",
    "CorrectiveActionStatus", "OSHALog", "SafetyDocument",
    "SafetyRiskAssessment", "SafetyScorecard",
    "EmployeeStatus", "PTOStatus", "PTOType", "ReviewRating",
    "EmployeeProfile", "TimeEntry", "PTORequest",
    "OnboardingChecklist", "OnboardingTask",
    "PerformanceReview", "HRTrainingRecord",
    "EmployeeDocument", "CompensationRecord", "SkillEntry",
    "BenefitPlan", "EmployeeBenefit",
    "AccountType", "Account", "JournalEntry", "JournalEntryLine",
    "AccountsPayable", "AccountsReceivable", "APStatus", "ARStatus",
    "PayPeriodType", "PayRunStatus", "PayPeriod", "PayRun",
    "PayStub", "PayDeduction", "TaxWithholding",
    "OnboardingWorkflowTemplate", "OnboardingWorkflowStep",
    "OnboardingWorkflowInstance", "OnboardingWorkflowStepInstance",
    "ScreeningProvider", "ScreeningStatus", "ScreeningRequest",
    "DrugScreenFacility", "DrugScreenAppointment",
    "CRMCompany", "CRMContact", "CRMContract", "CRMContractStatus",
    "CRMActivity", "CRMOutreachCampaign", "CRMOutreachRecipient",
    "CRMResearchResult", "CRMChatSession", "CRMChatMessage",
]


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    VOIDED = "voided"


class DispatchJobStatus(str, enum.Enum):
    UNASSIGNED = "unassigned"
    SCHEDULED = "scheduled"
    EN_ROUTE = "en_route"
    ON_SITE = "on_site"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrgType(str, enum.Enum):
    CONTRACTOR = "contractor"
    ISP_OWNER = "isp_owner"


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    BILLED = "billed"
    REWORK = "rework"
    FAILED_INSPECTION = "failed_inspection"


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    PM = "pm"
    FIELD_LEAD = "field_lead"
    CREW_MEMBER = "crew_member"
    INSPECTOR = "inspector"
    FINANCE = "finance"
    CLIENT_VIEWER = "client_viewer"


def gen_uuid():
    return str(uuid.uuid4())


class Org(Base):
    __tablename__ = "orgs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    org_type = Column(SAEnum(OrgType, name="org_type_enum"), nullable=False, default=OrgType.CONTRACTOR)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("OrgMember", back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("OrgMember", back_populates="user", cascade="all, delete-orphan")


class OrgMember(Base):
    __tablename__ = "org_members"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(SAEnum(RoleName, name="role_name_enum"), nullable=False, default=RoleName.CREW_MEMBER)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_user"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(ProjectStatus, name="project_status_enum"), default=ProjectStatus.PLANNING)
    owner_org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id"), nullable=True)
    executing_org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner_org = relationship("Org", foreign_keys=[owner_org_id])
    executing_org = relationship("Org", foreign_keys=[executing_org_id])
    work_packages = relationship("WorkPackage", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class WorkPackage(Base):
    __tablename__ = "work_packages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="work_packages")
    tasks = relationship("Task", back_populates="work_package")


class TaskType(Base):
    __tablename__ = "task_types"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=False, default="feet")
    color = Column(String(7), nullable=True, default="#3B82F6")
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("Task", back_populates="task_type")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    work_package_id = Column(UUID(as_uuid=False), ForeignKey("work_packages.id", ondelete="SET NULL"), nullable=True)
    task_type_id = Column(UUID(as_uuid=False), ForeignKey("task_types.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(TaskStatus, name="task_status_enum"), default=TaskStatus.NOT_STARTED)
    planned_qty = Column(Float, nullable=True)
    actual_qty = Column(Float, nullable=True, default=0)
    unit = Column(String(50), nullable=True)
    unit_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True, default=0)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    priority = Column(String(20), nullable=True, default="medium")
    due_date = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    geometry = Column(Geometry(srid=4326), nullable=True)
    style_color = Column(String(20), nullable=True)
    style_width = Column(Float, nullable=True)
    style_opacity = Column(Float, nullable=True)
    style_icon = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    work_package = relationship("WorkPackage", back_populates="tasks")
    task_type = relationship("TaskType", back_populates="tasks")
    field_entries = relationship("FieldEntry", back_populates="task", cascade="all, delete-orphan")
    assigned_user = relationship("User", foreign_keys=[assigned_to])

    __table_args__ = (
        Index("idx_task_geometry", "geometry", postgresql_using="gist"),
        Index("idx_task_project_status", "project_id", "status"),
    )


class FieldEntry(Base):
    __tablename__ = "field_entries"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    task_id = Column(UUID(as_uuid=False), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    qty_delta = Column(Float, nullable=True)
    labor_hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lon = Column(Float, nullable=True)
    gps_accuracy = Column(Float, nullable=True)
    offline_client_id = Column(String(255), nullable=True, unique=True)
    deviation_flags = Column(Text, nullable=True)
    deviation_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="field_entries")
    user = relationship("User")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    field_entry_id = Column(UUID(as_uuid=False), ForeignKey("field_entries.id", ondelete="CASCADE"), nullable=True)
    task_id = Column(UUID(as_uuid=False), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    field_entry = relationship("FieldEntry", backref="attachments")
    task = relationship("Task", backref="attachments")
    user = relationship("User")


class InspectionStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class InspectionTemplate(Base):
    __tablename__ = "inspection_templates"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    task_type_id = Column(UUID(as_uuid=False), ForeignKey("task_types.id"), nullable=True)
    checklist_items = Column(Text, nullable=True)
    require_photos = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    task_id = Column(UUID(as_uuid=False), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=False), ForeignKey("inspection_templates.id"), nullable=True)
    inspector_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(InspectionStatus, name="inspection_status_enum"), default=InspectionStatus.PENDING)
    checklist_results = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", backref="inspections")
    inspector = relationship("User")
    template = relationship("InspectionTemplate")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_created", "created_at"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_format = Column(String(50), nullable=False)
    total_features = Column(Integer, default=0)
    imported_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
    status = Column(String(50), default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")
    user = relationship("User")


class ProjectBudget(Base):
    __tablename__ = "project_budgets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    total_budget = Column(Float, default=0)
    labor_budget = Column(Float, default=0)
    material_budget = Column(Float, default=0)
    contingency_pct = Column(Float, default=10.0)
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", backref="budget")


class Material(Base):
    __tablename__ = "materials"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=True, unique=True)
    category = Column(String(100), nullable=True)
    unit = Column(String(50), default="each")
    unit_cost = Column(Float, nullable=True)
    stock_qty = Column(Float, default=0)
    min_stock_qty = Column(Float, default=0)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskMaterial(Base):
    __tablename__ = "task_materials"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    task_id = Column(UUID(as_uuid=False), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(UUID(as_uuid=False), ForeignKey("materials.id"), nullable=False)
    planned_qty = Column(Float, default=0)
    actual_qty = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", backref="materials_used")
    material = relationship("Material")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=True)
    entity_name = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")
    user = relationship("User")

    __table_args__ = (
        Index("idx_activity_project", "project_id", "created_at"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    current_version = Column(Integer, default=1)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    locked_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", backref="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    locker = relationship("User", foreign_keys=[locked_by])


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    change_notes = Column(Text, nullable=True)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", backref="versions")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class SavedMapView(Base):
    __tablename__ = "saved_map_views"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    center_lng = Column(Float, nullable=False)
    center_lat = Column(Float, nullable=False)
    zoom = Column(Float, nullable=False)
    bearing = Column(Float, default=0)
    pitch = Column(Float, default=0)
    filters = Column(Text, nullable=True)
    layer_visibility = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")
    user = relationship("User")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    phone = Column(String(30), nullable=True)
    title = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    avatar_url = Column(Text, nullable=True)
    timezone = Column(String(50), nullable=True, default="America/Chicago")
    notification_prefs = Column(Text, nullable=True)
    certifications = Column(Text, nullable=True)
    emergency_contact = Column(Text, nullable=True)
    hire_date = Column(DateTime, nullable=True)
    hourly_rate = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="profile")


class OrgInvite(Base):
    __tablename__ = "org_invites"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleName, name="role_name_enum", create_type=False), nullable=False, default=RoleName.CREW_MEMBER)
    invited_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    accepted = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    inviter = relationship("User", foreign_keys=[invited_by])


class RateCard(Base):
    __tablename__ = "rate_cards"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=False, default="each")
    unit_rate = Column(Float, nullable=False, default=0)
    labor_rate = Column(Float, nullable=True)
    material_rate = Column(Float, nullable=True)
    equipment_rate = Column(Float, nullable=True)
    permit_rate = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    effective_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id"), nullable=False)
    invoice_number = Column(String(50), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(InvoiceStatus, name="invoice_status_enum"), default=InvoiceStatus.DRAFT)
    billing_period_start = Column(DateTime, nullable=True)
    billing_period_end = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    subtotal = Column(Float, default=0)
    tax_rate = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    amount_paid = Column(Float, default=0)
    balance_due = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    terms = Column(Text, nullable=True)
    retainage_pct = Column(Float, default=0)
    retainage_amount = Column(Float, default=0)
    change_order_total = Column(Float, default=0)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project")
    org = relationship("Org")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_invoice_project", "project_id"),
        Index("idx_invoice_status", "status"),
    )


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=False), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    rate_card_id = Column(UUID(as_uuid=False), ForeignKey("rate_cards.id", ondelete="SET NULL"), nullable=True)
    line_number = Column(Integer, nullable=False, default=1)
    category = Column(String(50), nullable=False, default="labor")
    description = Column(Text, nullable=False)
    work_type = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=False, default="each")
    quantity = Column(Float, nullable=False, default=0)
    unit_rate = Column(Float, nullable=False, default=0)
    labor_cost = Column(Float, default=0)
    material_cost = Column(Float, default=0)
    equipment_cost = Column(Float, default=0)
    permit_cost = Column(Float, default=0)
    subcontractor_cost = Column(Float, default=0)
    other_cost = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    is_change_order = Column(Boolean, default=False)
    change_order_ref = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    billable = Column(Boolean, default=True)
    approved = Column(Boolean, default=False)
    work_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="line_items")
    task = relationship("Task")
    rate_card = relationship("RateCard")


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    co_number = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    reason = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")
    amount = Column(Float, default=0)
    labor_amount = Column(Float, default=0)
    material_amount = Column(Float, default=0)
    equipment_amount = Column(Float, default=0)
    requested_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=True)
    reference_number = Column(String(100), nullable=True)
    payment_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    recorded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="payments")
    recorder = relationship("User", foreign_keys=[recorded_by])


class Crew(Base):
    __tablename__ = "crews"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#3B82F6")
    vehicle = Column(String(100), nullable=True)
    skills = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    max_jobs_per_day = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    members = relationship("CrewMember", back_populates="crew", cascade="all, delete-orphan")
    jobs = relationship("DispatchJob", back_populates="crew")


class CrewMember(Base):
    __tablename__ = "crew_members"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    crew_id = Column(UUID(as_uuid=False), ForeignKey("crews.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_in_crew = Column(String(50), default="member")
    joined_at = Column(DateTime, default=datetime.utcnow)

    crew = relationship("Crew", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("crew_id", "user_id", name="uq_crew_user"),
    )


class DispatchJob(Base):
    __tablename__ = "dispatch_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=False), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    crew_id = Column(UUID(as_uuid=False), ForeignKey("crews.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(DispatchJobStatus, name="dispatch_job_status_enum"), default=DispatchJobStatus.UNASSIGNED)
    priority = Column(String(20), default="medium")
    job_type = Column(String(100), nullable=True)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    estimated_duration_hrs = Column(Float, nullable=True)
    location_address = Column(Text, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project")
    task = relationship("Task")
    crew = relationship("Crew", back_populates="jobs")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_dispatch_project", "project_id"),
        Index("idx_dispatch_crew_date", "crew_id", "scheduled_start"),
        Index("idx_dispatch_status", "status"),
    )


class AssetStatus(str, enum.Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"
    LOST = "lost"
    DAMAGED = "damaged"


class FleetVehicleStatus(str, enum.Enum):
    ACTIVE = "active"
    IN_SHOP = "in_shop"
    OUT_OF_SERVICE = "out_of_service"
    RETIRED = "retired"


class AssetCategory(Base):
    __tablename__ = "asset_categories"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    color = Column(String(7), default="#3B82F6")
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    assets = relationship("Asset", back_populates="category")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=False), ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    asset_tag = Column(String(100), nullable=True)
    serial_number = Column(String(255), nullable=True)
    make = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(AssetStatus, name="asset_status_enum"), default=AssetStatus.AVAILABLE)
    condition = Column(String(50), default="good")
    purchase_date = Column(DateTime, nullable=True)
    purchase_cost = Column(Float, default=0)
    current_value = Column(Float, default=0)
    depreciation_method = Column(String(50), default="straight_line")
    depreciation_rate = Column(Float, default=0)
    useful_life_years = Column(Float, default=5)
    salvage_value = Column(Float, default=0)
    warranty_expiry = Column(DateTime, nullable=True)
    location_description = Column(Text, nullable=True)
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    assigned_to_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_crew_id = Column(UUID(as_uuid=False), ForeignKey("crews.id", ondelete="SET NULL"), nullable=True)
    assigned_to_project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    image_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    custom_fields = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    category = relationship("AssetCategory", back_populates="assets")
    assigned_user = relationship("User", foreign_keys=[assigned_to_user_id])
    assigned_crew = relationship("Crew", foreign_keys=[assigned_to_crew_id])
    assigned_project = relationship("Project", foreign_keys=[assigned_to_project_id])
    allocations = relationship("AssetAllocation", back_populates="asset", order_by="AssetAllocation.start_at.desc()")
    incidents = relationship("AssetIncident", back_populates="asset", order_by="AssetIncident.occurred_at.desc()")
    maintenance_records = relationship("AssetMaintenance", back_populates="asset", order_by="AssetMaintenance.scheduled_at.desc()")

    __table_args__ = (
        Index("idx_asset_org", "org_id"),
        Index("idx_asset_status", "status"),
        Index("idx_asset_category", "category_id"),
        Index("idx_asset_assigned_user", "assigned_to_user_id"),
    )


class AssetAllocation(Base):
    __tablename__ = "asset_allocations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    asset_id = Column(UUID(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    assigned_to_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_crew_id = Column(UUID(as_uuid=False), ForeignKey("crews.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    start_at = Column(DateTime, default=datetime.utcnow)
    end_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    allocated_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    returned_condition = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="allocations")
    user = relationship("User", foreign_keys=[assigned_to_user_id])
    crew = relationship("Crew", foreign_keys=[assigned_to_crew_id])
    project = relationship("Project")
    allocator = relationship("User", foreign_keys=[allocated_by])

    __table_args__ = (
        Index("idx_allocation_asset", "asset_id"),
        Index("idx_allocation_dates", "start_at", "end_at"),
    )


class AssetIncident(Base):
    __tablename__ = "asset_incidents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    asset_id = Column(UUID(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    reported_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    incident_type = Column(String(100), nullable=False)
    severity = Column(String(20), default="medium")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    location_description = Column(Text, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    damage_cost = Column(Float, default=0)
    resolution = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="open")
    photos = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="incidents")
    reporter = relationship("User", foreign_keys=[reported_by])

    __table_args__ = (
        Index("idx_incident_asset", "asset_id"),
        Index("idx_incident_severity", "severity"),
    )


class AssetMaintenance(Base):
    __tablename__ = "asset_maintenance"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    asset_id = Column(UUID(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    maintenance_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    vendor = Column(String(255), nullable=True)
    cost = Column(Float, default=0)
    status = Column(String(50), default="scheduled")
    performed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    next_due_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="maintenance_records")
    performer = relationship("User", foreign_keys=[performed_by])

    __table_args__ = (
        Index("idx_maintenance_asset", "asset_id"),
        Index("idx_maintenance_status", "status"),
    )


class FleetVehicle(Base):
    __tablename__ = "fleet_vehicles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(UUID(as_uuid=False), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    vin = Column(String(20), nullable=True)
    make = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    year = Column(Integer, nullable=True)
    license_plate = Column(String(20), nullable=True)
    color = Column(String(50), nullable=True)
    vehicle_type = Column(String(100), default="truck")
    status = Column(SAEnum(FleetVehicleStatus, name="fleet_vehicle_status_enum"), default=FleetVehicleStatus.ACTIVE)
    assigned_driver_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_crew_id = Column(UUID(as_uuid=False), ForeignKey("crews.id", ondelete="SET NULL"), nullable=True)
    current_location = Column(Geometry("POINT", srid=4326), nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    current_speed = Column(Float, default=0)
    current_heading = Column(Float, default=0)
    odometer = Column(Float, default=0)
    fuel_level = Column(Float, nullable=True)
    engine_hours = Column(Float, default=0)
    last_location_update = Column(DateTime, nullable=True)
    telematics_provider = Column(String(50), nullable=True)
    telematics_vehicle_id = Column(String(255), nullable=True)
    insurance_expiry = Column(DateTime, nullable=True)
    registration_expiry = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    asset = relationship("Asset")
    driver = relationship("User", foreign_keys=[assigned_driver_id])
    crew = relationship("Crew", foreign_keys=[assigned_crew_id])
    telemetry = relationship("FleetTelemetry", back_populates="vehicle", order_by="FleetTelemetry.event_time.desc()")

    __table_args__ = (
        Index("idx_fleet_org", "org_id"),
        Index("idx_fleet_status", "status"),
        Index("idx_fleet_driver", "assigned_driver_id"),
    )


class FleetTelemetry(Base):
    __tablename__ = "fleet_telemetry"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    vehicle_id = Column(UUID(as_uuid=False), ForeignKey("fleet_vehicles.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    speed = Column(Float, default=0)
    heading = Column(Float, default=0)
    odometer = Column(Float, nullable=True)
    fuel_level = Column(Float, nullable=True)
    engine_status = Column(String(20), nullable=True)
    event_type = Column(String(100), nullable=True)
    event_time = Column(DateTime, default=datetime.utcnow)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("FleetVehicle", back_populates="telemetry")

    __table_args__ = (
        Index("idx_telemetry_vehicle", "vehicle_id"),
        Index("idx_telemetry_time", "event_time"),
    )


class TechnicianLocation(Base):
    __tablename__ = "technician_locations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    source = Column(String(50), default="mobile_checkin")
    device_info = Column(Text, nullable=True)
    battery_level = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    event_time = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    org = relationship("Org")

    __table_args__ = (
        Index("idx_tech_loc_user", "user_id"),
        Index("idx_tech_loc_org", "org_id"),
        Index("idx_tech_loc_time", "event_time"),
        Index("idx_tech_loc_active", "is_active"),
    )


class TelematicsIntegration(Base):
    __tablename__ = "telematics_integrations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    display_name = Column(String(255), nullable=True)
    api_endpoint = Column(Text, nullable=True)
    api_key_ref = Column(String(255), nullable=True)
    database_name = Column(String(255), nullable=True)
    account_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime, nullable=True)
    sync_interval_minutes = Column(Integer, default=5)
    vehicle_count = Column(Integer, default=0)
    status = Column(String(50), default="configured")
    error_message = Column(Text, nullable=True)
    config_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")

    __table_args__ = (
        Index("idx_telematics_org", "org_id"),
        UniqueConstraint("org_id", "provider", name="uq_org_provider"),
    )


class SafetyIncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CORRECTIVE_ACTION = "corrective_action"
    CLOSED = "closed"


class SafetyIncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CorrectiveActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    OVERDUE = "overdue"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"
    ONBOARDING = "onboarding"


class PTOStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


class PTOType(str, enum.Enum):
    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    FMLA = "fmla"
    UNPAID = "unpaid"


class ReviewRating(str, enum.Enum):
    EXCEEDS = "exceeds_expectations"
    MEETS = "meets_expectations"
    NEEDS_IMPROVEMENT = "needs_improvement"
    UNSATISFACTORY = "unsatisfactory"


class SafetyIncident(Base):
    __tablename__ = "safety_incidents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    reported_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    incident_type = Column(String(100), nullable=False)
    severity = Column(SAEnum(SafetyIncidentSeverity, name="safety_severity_enum"), default=SafetyIncidentSeverity.MEDIUM)
    status = Column(SAEnum(SafetyIncidentStatus, name="safety_incident_status_enum"), default=SafetyIncidentStatus.OPEN)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    location_description = Column(Text, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    is_near_miss = Column(Boolean, default=False)
    is_osha_recordable = Column(Boolean, default=False)
    days_away = Column(Integer, default=0)
    days_restricted = Column(Integer, default=0)
    medical_treatment = Column(Boolean, default=False)
    injury_type = Column(String(100), nullable=True)
    body_part = Column(String(100), nullable=True)
    witnesses = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    immediate_actions = Column(Text, nullable=True)
    photos = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    reporter = relationship("User", foreign_keys=[reported_by])
    project = relationship("Project")

    __table_args__ = (
        Index("idx_safety_incident_org", "org_id"),
        Index("idx_safety_incident_status", "status"),
        Index("idx_safety_incident_severity", "severity"),
        Index("idx_safety_incident_date", "occurred_at"),
    )


class SafetyInspectionTemplate(Base):
    __tablename__ = "safety_inspection_templates"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    checklist_items = Column(Text, nullable=True)
    frequency = Column(String(50), default="daily")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")


class SafetyInspectionRecord(Base):
    __tablename__ = "safety_inspection_records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=False), ForeignKey("safety_inspection_templates.id", ondelete="SET NULL"), nullable=True)
    inspector_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="completed")
    checklist_results = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    findings = Column(Text, nullable=True)
    conducted_at = Column(DateTime, default=datetime.utcnow)
    location_description = Column(Text, nullable=True)
    photos = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    template = relationship("SafetyInspectionTemplate")
    inspector = relationship("User", foreign_keys=[inspector_id])
    project = relationship("Project")

    __table_args__ = (
        Index("idx_safety_insp_org", "org_id"),
        Index("idx_safety_insp_date", "conducted_at"),
    )


class ToolboxTalk(Base):
    __tablename__ = "toolbox_talks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    presenter_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    topic = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    duration_minutes = Column(Integer, default=15)
    conducted_at = Column(DateTime, default=datetime.utcnow)
    attendee_count = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    presenter = relationship("User", foreign_keys=[presenter_id])
    project = relationship("Project")
    attendance = relationship("ToolboxTalkAttendance", back_populates="talk", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_toolbox_org", "org_id"),
        Index("idx_toolbox_date", "conducted_at"),
    )


class ToolboxTalkAttendance(Base):
    __tablename__ = "toolbox_talk_attendance"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    talk_id = Column(UUID(as_uuid=False), ForeignKey("toolbox_talks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    attended = Column(Boolean, default=True)
    signature = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    talk = relationship("ToolboxTalk", back_populates="attendance")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("talk_id", "user_id", name="uq_talk_user"),
    )


class SafetyTraining(Base):
    __tablename__ = "safety_trainings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    training_name = Column(String(255), nullable=False)
    training_type = Column(String(100), nullable=True)
    provider = Column(String(255), nullable=True)
    completion_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    certificate_number = Column(String(255), nullable=True)
    status = Column(String(50), default="completed")
    score = Column(Float, nullable=True)
    hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User")

    __table_args__ = (
        Index("idx_safety_training_org", "org_id"),
        Index("idx_safety_training_user", "user_id"),
        Index("idx_safety_training_expiry", "expiry_date"),
    )


class PPECompliance(Base):
    __tablename__ = "ppe_compliance"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    ppe_type = Column(String(100), nullable=False)
    status = Column(String(50), default="compliant")
    issued_at = Column(DateTime, nullable=True)
    last_inspected_at = Column(DateTime, nullable=True)
    next_inspection_due = Column(DateTime, nullable=True)
    condition = Column(String(50), default="good")
    serial_number = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User")

    __table_args__ = (
        Index("idx_ppe_org", "org_id"),
        Index("idx_ppe_user", "user_id"),
    )


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    incident_id = Column(UUID(as_uuid=False), ForeignKey("safety_incidents.id", ondelete="SET NULL"), nullable=True)
    inspection_id = Column(UUID(as_uuid=False), ForeignKey("safety_inspection_records.id", ondelete="SET NULL"), nullable=True)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    action_type = Column(String(100), default="corrective")
    priority = Column(String(20), default="medium")
    status = Column(SAEnum(CorrectiveActionStatus, name="corrective_action_status_enum"), default=CorrectiveActionStatus.OPEN)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    verified_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    root_cause_category = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    incident = relationship("SafetyIncident")
    inspection = relationship("SafetyInspectionRecord")
    assignee = relationship("User", foreign_keys=[assigned_to])
    verifier = relationship("User", foreign_keys=[verified_by])

    __table_args__ = (
        Index("idx_corrective_org", "org_id"),
        Index("idx_corrective_status", "status"),
        Index("idx_corrective_due", "due_date"),
    )


class OSHALog(Base):
    __tablename__ = "osha_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    year = Column(Integer, nullable=False)
    total_hours_worked = Column(Float, default=0)
    total_employees = Column(Integer, default=0)
    total_incidents = Column(Integer, default=0)
    recordable_cases = Column(Integer, default=0)
    dart_cases = Column(Integer, default=0)
    fatalities = Column(Integer, default=0)
    trir = Column(Float, default=0)
    dart_rate = Column(Float, default=0)
    emr = Column(Float, default=1.0)
    days_away = Column(Integer, default=0)
    days_restricted = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")

    __table_args__ = (
        Index("idx_osha_org_year", "org_id", "year"),
    )


class SafetyDocument(Base):
    __tablename__ = "safety_documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(100), nullable=True)
    version = Column(String(50), default="1.0")
    effective_date = Column(DateTime, nullable=True)
    review_date = Column(DateTime, nullable=True)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    uploader = relationship("User", foreign_keys=[uploaded_by])

    __table_args__ = (
        Index("idx_safety_doc_org", "org_id"),
    )


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(String(50), nullable=True)
    job_title = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    supervisor_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    status = Column(SAEnum(EmployeeStatus, name="employee_status_enum"), default=EmployeeStatus.ACTIVE)
    hire_date = Column(DateTime, nullable=True)
    termination_date = Column(DateTime, nullable=True)
    employment_type = Column(String(50), default="full_time")
    phone = Column(String(30), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    emergency_contact_relation = Column(String(100), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    drivers_license = Column(String(50), nullable=True)
    dl_expiry = Column(DateTime, nullable=True)
    cdl_class = Column(String(10), nullable=True)
    medical_card_expiry = Column(DateTime, nullable=True)
    shirt_size = Column(String(10), nullable=True)
    boot_size = Column(String(10), nullable=True)
    skills_json = Column(Text, nullable=True)
    certifications_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    pto_balance_vacation = Column(Float, default=0)
    pto_balance_sick = Column(Float, default=0)
    pto_balance_personal = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User", foreign_keys=[user_id])
    supervisor = relationship("User", foreign_keys=[supervisor_id])

    __table_args__ = (
        Index("idx_emp_org", "org_id"),
        Index("idx_emp_user", "user_id"),
        Index("idx_emp_status", "status"),
        Index("idx_emp_department", "department"),
        UniqueConstraint("org_id", "user_id", name="uq_emp_org_user"),
    )


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    clock_in = Column(DateTime, nullable=False)
    clock_out = Column(DateTime, nullable=True)
    break_minutes = Column(Integer, default=0)
    total_hours = Column(Float, nullable=True)
    overtime_hours = Column(Float, default=0)
    entry_type = Column(String(50), default="regular")
    source = Column(String(50), default="manual")
    geo_lat_in = Column(Float, nullable=True)
    geo_lng_in = Column(Float, nullable=True)
    geo_lat_out = Column(Float, nullable=True)
    geo_lng_out = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    approved = Column(Boolean, default=False)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project")
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        Index("idx_time_org", "org_id"),
        Index("idx_time_user", "user_id"),
        Index("idx_time_date", "clock_in"),
    )


class PTORequest(Base):
    __tablename__ = "pto_requests"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    pto_type = Column(SAEnum(PTOType, name="pto_type_enum"), default=PTOType.VACATION)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_days = Column(Float, default=1)
    status = Column(SAEnum(PTOStatus, name="pto_status_enum"), default=PTOStatus.PENDING)
    reason = Column(Text, nullable=True)
    approver_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    denial_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approver_id])

    __table_args__ = (
        Index("idx_pto_org", "org_id"),
        Index("idx_pto_user", "user_id"),
        Index("idx_pto_status", "status"),
        Index("idx_pto_dates", "start_date", "end_date"),
    )


class OnboardingChecklist(Base):
    __tablename__ = "onboarding_checklists"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    tasks = relationship("OnboardingTask", back_populates="checklist", cascade="all, delete-orphan")


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    checklist_id = Column(UUID(as_uuid=False), ForeignKey("onboarding_checklists.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    due_days = Column(Integer, default=7)
    status = Column(String(50), default="pending")
    completed_at = Column(DateTime, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    checklist = relationship("OnboardingChecklist", back_populates="tasks")
    employee = relationship("User", foreign_keys=[employee_id])
    assignee = relationship("User", foreign_keys=[assigned_to])


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    review_date = Column(DateTime, default=datetime.utcnow)
    overall_rating = Column(SAEnum(ReviewRating, name="review_rating_enum"), nullable=True)
    technical_score = Column(Float, nullable=True)
    safety_score = Column(Float, nullable=True)
    teamwork_score = Column(Float, nullable=True)
    attendance_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    employee_comments = Column(Text, nullable=True)
    reviewer_comments = Column(Text, nullable=True)
    status = Column(String(50), default="draft")
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        Index("idx_review_org", "org_id"),
        Index("idx_review_user", "user_id"),
        Index("idx_review_date", "review_date"),
    )


class HRTrainingRecord(Base):
    __tablename__ = "hr_training_records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    training_name = Column(String(255), nullable=False)
    training_type = Column(String(100), nullable=True)
    provider = Column(String(255), nullable=True)
    completion_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    certificate_number = Column(String(255), nullable=True)
    status = Column(String(50), default="completed")
    required = Column(Boolean, default=False)
    cost = Column(Float, default=0)
    hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User")

    __table_args__ = (
        Index("idx_hr_training_org", "org_id"),
        Index("idx_hr_training_user", "user_id"),
    )


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(100), nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    employee = relationship("User", foreign_keys=[user_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])

    __table_args__ = (
        Index("idx_emp_doc_org", "org_id"),
        Index("idx_emp_doc_user", "user_id"),
    )


class CompensationRecord(Base):
    __tablename__ = "compensation_records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    pay_type = Column(String(50), default="hourly")
    hourly_rate = Column(Float, nullable=True)
    salary = Column(Float, nullable=True)
    overtime_rate = Column(Float, nullable=True)
    per_diem = Column(Float, nullable=True)
    effective_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    reason = Column(String(255), nullable=True)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        Index("idx_comp_org", "org_id"),
        Index("idx_comp_user", "user_id"),
    )


class SkillEntry(Base):
    __tablename__ = "skill_entries"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    skill_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    proficiency_level = Column(Integer, default=1)
    years_experience = Column(Float, nullable=True)
    last_used = Column(DateTime, nullable=True)
    certified = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User")

    __table_args__ = (
        Index("idx_skill_org", "org_id"),
        Index("idx_skill_user", "user_id"),
    )


class SafetyRiskAssessment(Base):
    __tablename__ = "safety_risk_assessments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    assessment_date = Column(DateTime, default=datetime.utcnow)
    risk_level = Column(String(20), default="medium")
    likelihood = Column(Integer, default=3)
    severity = Column(Integer, default=3)
    risk_score = Column(Integer, default=9)
    hazard_type = Column(String(100), nullable=True)
    control_measures = Column(Text, nullable=True)
    residual_risk_level = Column(String(20), nullable=True)
    residual_risk_score = Column(Integer, nullable=True)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    review_date = Column(DateTime, nullable=True)
    next_review_date = Column(DateTime, nullable=True)
    status = Column(String(20), default="open")
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    project = relationship("Project")
    assignee = relationship("User", foreign_keys=[assigned_to])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_risk_assess_org", "org_id"),
        Index("idx_risk_assess_project", "project_id"),
    )


class SafetyScorecard(Base):
    __tablename__ = "safety_scorecards"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_hours_worked = Column(Float, default=0)
    total_incidents = Column(Integer, default=0)
    recordable_incidents = Column(Integer, default=0)
    lost_time_incidents = Column(Integer, default=0)
    near_misses = Column(Integer, default=0)
    first_aid_cases = Column(Integer, default=0)
    trir = Column(Float, default=0)
    dart_rate = Column(Float, default=0)
    emr = Column(Float, default=1.0)
    severity_rate = Column(Float, default=0)
    training_compliance_pct = Column(Float, default=0)
    inspection_completion_pct = Column(Float, default=0)
    corrective_action_closure_pct = Column(Float, default=0)
    safety_score = Column(Float, default=0)
    grade = Column(String(5), default="C")
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    creator = relationship("User")

    __table_args__ = (
        Index("idx_scorecard_org", "org_id"),
        Index("idx_scorecard_period", "period_start", "period_end"),
    )


class BenefitPlan(Base):
    __tablename__ = "benefit_plans"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    plan_type = Column(String(50), nullable=False)
    provider = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    employer_contribution = Column(Float, default=0)
    employee_contribution = Column(Float, default=0)
    coverage_details = Column(Text, nullable=True)
    effective_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")

    __table_args__ = (
        Index("idx_benefit_plan_org", "org_id"),
    )


class EmployeeBenefit(Base):
    __tablename__ = "employee_benefits"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=False), ForeignKey("benefit_plans.id"), nullable=False)
    enrollment_date = Column(DateTime, nullable=False)
    coverage_level = Column(String(50), default="individual")
    dependents_count = Column(Integer, default=0)
    employee_cost = Column(Float, default=0)
    employer_cost = Column(Float, default=0)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User")
    plan = relationship("BenefitPlan")

    __table_args__ = (
        Index("idx_emp_benefit_org", "org_id"),
        Index("idx_emp_benefit_user", "user_id"),
    )


class AccountType(str, enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class APStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    OVERDUE = "overdue"
    VOIDED = "voided"


class ARStatus(str, enum.Enum):
    OUTSTANDING = "outstanding"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    WRITTEN_OFF = "written_off"


class Account(Base):
    __tablename__ = "chart_of_accounts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    account_number = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    account_type = Column(SAEnum(AccountType), nullable=False)
    parent_id = Column(UUID(as_uuid=False), ForeignKey("chart_of_accounts.id"), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    normal_balance = Column(String(10), default="debit")
    balance = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    parent = relationship("Account", remote_side="Account.id")

    __table_args__ = (
        Index("idx_acct_org", "org_id"),
        UniqueConstraint("org_id", "account_number", name="uq_acct_number"),
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    entry_number = Column(String(50), nullable=False)
    entry_date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)
    reference = Column(String(255), nullable=True)
    source = Column(String(50), default="manual")
    is_posted = Column(Boolean, default=False)
    is_reversing = Column(Boolean, default=False)
    reversed_entry_id = Column(UUID(as_uuid=False), nullable=True)
    total_debit = Column(Float, default=0)
    total_credit = Column(Float, default=0)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        Index("idx_je_org", "org_id"),
        Index("idx_je_date", "entry_date"),
    )


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    entry_id = Column(UUID(as_uuid=False), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(UUID(as_uuid=False), ForeignKey("chart_of_accounts.id"), nullable=False)
    description = Column(String(255), nullable=True)
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)

    entry = relationship("JournalEntry")
    account = relationship("Account")
    project = relationship("Project")

    __table_args__ = (
        Index("idx_jel_entry", "entry_id"),
        Index("idx_jel_account", "account_id"),
    )


class AccountsPayable(Base):
    __tablename__ = "accounts_payable"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    vendor_name = Column(String(255), nullable=False)
    vendor_contact = Column(String(255), nullable=True)
    invoice_number = Column(String(100), nullable=False)
    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    amount_paid = Column(Float, default=0)
    status = Column(SAEnum(APStatus), default=APStatus.PENDING)
    account_id = Column(UUID(as_uuid=False), ForeignKey("chart_of_accounts.id"), nullable=True)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    description = Column(Text, nullable=True)
    payment_terms = Column(String(50), nullable=True)
    payment_method = Column(String(50), nullable=True)
    paid_date = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    account = relationship("Account")
    project = relationship("Project")
    creator = relationship("User")

    __table_args__ = (
        Index("idx_ap_org", "org_id"),
        Index("idx_ap_status", "status"),
        Index("idx_ap_due", "due_date"),
    )


class AccountsReceivable(Base):
    __tablename__ = "accounts_receivable"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    customer_name = Column(String(255), nullable=False)
    customer_contact = Column(String(255), nullable=True)
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id"), nullable=True)
    invoice_number = Column(String(100), nullable=False)
    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    amount_received = Column(Float, default=0)
    status = Column(SAEnum(ARStatus), default=ARStatus.OUTSTANDING)
    account_id = Column(UUID(as_uuid=False), ForeignKey("chart_of_accounts.id"), nullable=True)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    description = Column(Text, nullable=True)
    payment_terms = Column(String(50), nullable=True)
    last_payment_date = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    account = relationship("Account")
    project = relationship("Project")
    invoice = relationship("Invoice")
    creator = relationship("User")

    __table_args__ = (
        Index("idx_ar_org", "org_id"),
        Index("idx_ar_status", "status"),
        Index("idx_ar_due", "due_date"),
    )


class PayPeriodType(str, enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"


class PayRunStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    APPROVED = "approved"
    PAID = "paid"
    VOIDED = "voided"


class PayPeriod(Base):
    __tablename__ = "pay_periods"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    period_type = Column(SAEnum(PayPeriodType), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    pay_date = Column(DateTime, nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")

    __table_args__ = (
        Index("idx_payperiod_org", "org_id"),
        Index("idx_payperiod_dates", "start_date", "end_date"),
    )


class PayRun(Base):
    __tablename__ = "pay_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    pay_period_id = Column(UUID(as_uuid=False), ForeignKey("pay_periods.id"), nullable=False)
    run_number = Column(String(50), nullable=False)
    status = Column(SAEnum(PayRunStatus), default=PayRunStatus.DRAFT)
    total_gross = Column(Float, default=0)
    total_deductions = Column(Float, default=0)
    total_taxes = Column(Float, default=0)
    total_net = Column(Float, default=0)
    employee_count = Column(Integer, default=0)
    processed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    pay_period = relationship("PayPeriod")
    processor = relationship("User", foreign_keys=[processed_by])
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        Index("idx_payrun_org", "org_id"),
        Index("idx_payrun_period", "pay_period_id"),
    )


class PayStub(Base):
    __tablename__ = "pay_stubs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    pay_run_id = Column(UUID(as_uuid=False), ForeignKey("pay_runs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    holiday_hours = Column(Float, default=0)
    pto_hours = Column(Float, default=0)
    regular_pay = Column(Float, default=0)
    overtime_pay = Column(Float, default=0)
    holiday_pay = Column(Float, default=0)
    pto_pay = Column(Float, default=0)
    bonus = Column(Float, default=0)
    per_diem = Column(Float, default=0)
    gross_pay = Column(Float, default=0)
    total_deductions = Column(Float, default=0)
    total_taxes = Column(Float, default=0)
    net_pay = Column(Float, default=0)
    ytd_gross = Column(Float, default=0)
    ytd_taxes = Column(Float, default=0)
    ytd_net = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    pay_run = relationship("PayRun")
    user = relationship("User")

    __table_args__ = (
        Index("idx_paystub_org", "org_id"),
        Index("idx_paystub_user", "user_id"),
        Index("idx_paystub_run", "pay_run_id"),
    )


class PayDeduction(Base):
    __tablename__ = "pay_deductions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    pay_stub_id = Column(UUID(as_uuid=False), ForeignKey("pay_stubs.id", ondelete="CASCADE"), nullable=False)
    deduction_type = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    is_pretax = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    pay_stub = relationship("PayStub")

    __table_args__ = (
        Index("idx_payded_stub", "pay_stub_id"),
    )


class TaxWithholding(Base):
    __tablename__ = "tax_withholdings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    pay_stub_id = Column(UUID(as_uuid=False), ForeignKey("pay_stubs.id", ondelete="CASCADE"), nullable=False)
    tax_type = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    taxable_amount = Column(Float, default=0)
    rate = Column(Float, default=0)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    pay_stub = relationship("PayStub")

    __table_args__ = (
        Index("idx_taxwh_stub", "pay_stub_id"),
    )


class OnboardingWorkflowTemplate(Base):
    __tablename__ = "onboarding_workflow_templates"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    role_type = Column(String(100), nullable=True)
    estimated_days = Column(Integer, default=14)
    is_active = Column(Boolean, default=True)
    auto_assign_screening = Column(Boolean, default=True)
    auto_assign_drug_test = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    creator = relationship("User")

    __table_args__ = (
        Index("idx_obwt_org", "org_id"),
    )


class OnboardingWorkflowStep(Base):
    __tablename__ = "onboarding_workflow_steps"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    template_id = Column(UUID(as_uuid=False), ForeignKey("onboarding_workflow_templates.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    step_type = Column(String(50), default="task")
    is_required = Column(Boolean, default=True)
    auto_trigger = Column(Boolean, default=False)
    trigger_action = Column(String(100), nullable=True)
    due_days_offset = Column(Integer, default=0)
    assigned_role = Column(String(50), nullable=True)
    documents_required = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    template = relationship("OnboardingWorkflowTemplate")

    __table_args__ = (
        Index("idx_obws_template", "template_id"),
    )


class OnboardingWorkflowInstance(Base):
    __tablename__ = "onboarding_workflow_instances"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=False), ForeignKey("onboarding_workflow_templates.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="active")
    start_date = Column(DateTime, default=datetime.utcnow)
    target_completion = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    progress_pct = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    template = relationship("OnboardingWorkflowTemplate")
    employee = relationship("User", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[assigned_to])

    __table_args__ = (
        Index("idx_obwi_org", "org_id"),
        Index("idx_obwi_user", "user_id"),
    )


class OnboardingWorkflowStepInstance(Base):
    __tablename__ = "onboarding_workflow_step_instances"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    instance_id = Column(UUID(as_uuid=False), ForeignKey("onboarding_workflow_instances.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(UUID(as_uuid=False), ForeignKey("onboarding_workflow_steps.id"), nullable=False)
    status = Column(String(20), default="pending")
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    documents_uploaded = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    instance = relationship("OnboardingWorkflowInstance")
    step = relationship("OnboardingWorkflowStep")
    assignee = relationship("User", foreign_keys=[assigned_to])
    completer = relationship("User", foreign_keys=[completed_by])

    __table_args__ = (
        Index("idx_obwsi_instance", "instance_id"),
    )


class ScreeningProvider(str, enum.Enum):
    CHECKR = "checkr"
    CRIMSHIELD = "crimshield"
    STERLING = "sterling"
    HIRERIGHT = "hireright"
    GOODHIRE = "goodhire"
    ACCURATE = "accurate"


class ScreeningStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class ScreeningRequest(Base):
    __tablename__ = "screening_requests"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    screening_type = Column(String(50), nullable=False)
    provider = Column(SAEnum(ScreeningProvider), nullable=False)
    provider_request_id = Column(String(255), nullable=True)
    status = Column(SAEnum(ScreeningStatus), default=ScreeningStatus.PENDING)
    package_name = Column(String(255), nullable=True)
    requested_date = Column(DateTime, default=datetime.utcnow)
    completed_date = Column(DateTime, nullable=True)
    result = Column(String(50), nullable=True)
    result_details = Column(Text, nullable=True)
    report_url = Column(String(500), nullable=True)
    adjudication = Column(String(50), nullable=True)
    cost = Column(Float, nullable=True)
    requested_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    candidate = relationship("User", foreign_keys=[user_id])
    requester = relationship("User", foreign_keys=[requested_by])

    __table_args__ = (
        Index("idx_screening_org", "org_id"),
        Index("idx_screening_user", "user_id"),
        Index("idx_screening_status", "status"),
    )


class DrugScreenFacility(Base):
    __tablename__ = "drug_screen_facilities"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    facility_type = Column(String(50), default="concentra")
    address = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    zip_code = Column(String(20), nullable=False)
    phone = Column(String(50), nullable=True)
    fax = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    hours = Column(Text, nullable=True)
    accepts_walk_ins = Column(Boolean, default=True)
    services = Column(Text, nullable=True)
    network = Column(String(100), nullable=True)
    is_verified = Column(Boolean, default=False)
    last_verified = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_facility_zip", "zip_code"),
        Index("idx_facility_city_state", "city", "state"),
    )


class DrugScreenAppointment(Base):
    __tablename__ = "drug_screen_appointments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    facility_id = Column(UUID(as_uuid=False), ForeignKey("drug_screen_facilities.id"), nullable=False)
    screening_request_id = Column(UUID(as_uuid=False), ForeignKey("screening_requests.id"), nullable=True)
    test_type = Column(String(50), default="urine_5_panel")
    scheduled_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="scheduled")
    result = Column(String(20), nullable=True)
    result_date = Column(DateTime, nullable=True)
    chain_of_custody_number = Column(String(100), nullable=True)
    mro_name = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    candidate = relationship("User", foreign_keys=[user_id])
    facility = relationship("DrugScreenFacility")
    screening = relationship("ScreeningRequest")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_drugappt_org", "org_id"),
        Index("idx_drugappt_user", "user_id"),
    )


class CRMCompany(Base):
    __tablename__ = "crm_companies"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=True)
    company_type = Column(String(50), default="prospect")
    website = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(100), default="US")
    annual_revenue = Column(Float, nullable=True)
    employee_count = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)
    lead_source = Column(String(100), nullable=True)
    lifecycle_stage = Column(String(50), default="lead")
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    parent_company_id = Column(UUID(as_uuid=False), ForeignKey("crm_companies.id"), nullable=True)
    last_activity_date = Column(DateTime, nullable=True)
    custom_fields = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    owner = relationship("User", foreign_keys=[owner_id])
    parent_company = relationship("CRMCompany", remote_side="CRMCompany.id")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_crm_company_org", "org_id"),
        Index("idx_crm_company_type", "company_type"),
        Index("idx_crm_company_stage", "lifecycle_stage"),
    )


class CRMContact(Base):
    __tablename__ = "crm_contacts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=False), ForeignKey("crm_companies.id"), nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    mobile = Column(String(50), nullable=True)
    title = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    lead_status = Column(String(50), default="new")
    lifecycle_stage = Column(String(50), default="lead")
    lead_source = Column(String(100), nullable=True)
    lead_score = Column(Integer, default=0)
    tags = Column(Text, nullable=True)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    last_contacted = Column(DateTime, nullable=True)
    last_activity_date = Column(DateTime, nullable=True)
    do_not_contact = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    custom_fields = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    company = relationship("CRMCompany")
    owner = relationship("User", foreign_keys=[owner_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_crm_contact_org", "org_id"),
        Index("idx_crm_contact_company", "company_id"),
        Index("idx_crm_contact_status", "lead_status"),
        Index("idx_crm_contact_stage", "lifecycle_stage"),
    )


class CRMContractStatus(str, enum.Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    NEGOTIATION = "negotiation"
    APPROVED = "approved"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CRMContract(Base):
    __tablename__ = "crm_contracts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=False), ForeignKey("crm_companies.id"), nullable=True)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("crm_contacts.id"), nullable=True)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    contract_number = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    contract_type = Column(String(50), default="fixed_price")
    status = Column(SAEnum(CRMContractStatus), default=CRMContractStatus.DRAFT)
    value = Column(Float, default=0)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    signed_date = Column(DateTime, nullable=True)
    payment_terms = Column(String(100), nullable=True)
    billing_frequency = Column(String(50), nullable=True)
    scope_of_work = Column(Text, nullable=True)
    terms_conditions = Column(Text, nullable=True)
    renewal_date = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, default=False)
    margin_pct = Column(Float, nullable=True)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    signed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    tags = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    company = relationship("CRMCompany")
    contact = relationship("CRMContact")
    project = relationship("Project")
    owner = relationship("User", foreign_keys=[owner_id])
    signer = relationship("User", foreign_keys=[signed_by])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_crm_contract_org", "org_id"),
        Index("idx_crm_contract_company", "company_id"),
        Index("idx_crm_contract_status", "status"),
    )


class CRMActivity(Base):
    __tablename__ = "crm_activities"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("crm_contacts.id"), nullable=True)
    company_id = Column(UUID(as_uuid=False), ForeignKey("crm_companies.id"), nullable=True)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("crm_contracts.id"), nullable=True)
    activity_type = Column(String(50), nullable=False)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    outcome = Column(String(100), nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    is_completed = Column(Boolean, default=False)
    priority = Column(String(20), default="normal")
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    contact = relationship("CRMContact")
    company = relationship("CRMCompany")
    contract = relationship("CRMContract")
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])

    __table_args__ = (
        Index("idx_crm_activity_org", "org_id"),
        Index("idx_crm_activity_contact", "contact_id"),
        Index("idx_crm_activity_company", "company_id"),
    )


class CRMOutreachCampaign(Base):
    __tablename__ = "crm_outreach_campaigns"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    campaign_type = Column(String(50), default="email")
    status = Column(String(20), default="draft")
    subject = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    target_audience = Column(Text, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    sent_date = Column(DateTime, nullable=True)
    total_recipients = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)
    total_bounced = Column(Integer, default=0)
    open_rate = Column(Float, default=0)
    click_rate = Column(Float, default=0)
    reply_rate = Column(Float, default=0)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    creator = relationship("User")

    __table_args__ = (
        Index("idx_crm_campaign_org", "org_id"),
    )


class CRMOutreachRecipient(Base):
    __tablename__ = "crm_outreach_recipients"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    campaign_id = Column(UUID(as_uuid=False), ForeignKey("crm_outreach_campaigns.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("crm_contacts.id"), nullable=False)
    status = Column(String(20), default="pending")
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    bounced = Column(Boolean, default=False)
    unsubscribed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("CRMOutreachCampaign")
    contact = relationship("CRMContact")

    __table_args__ = (
        Index("idx_crm_recipient_campaign", "campaign_id"),
        Index("idx_crm_recipient_contact", "contact_id"),
    )


class CRMResearchResult(Base):
    __tablename__ = "crm_research_results"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("crm_contacts.id"), nullable=True)
    company_id = Column(UUID(as_uuid=False), ForeignKey("crm_companies.id"), nullable=True)
    research_type = Column(String(50), nullable=False)
    query = Column(Text, nullable=False)
    result_summary = Column(Text, nullable=True)
    result_data = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    sources = Column(Text, nullable=True)
    ai_model = Column(String(50), nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Org")
    contact = relationship("CRMContact")
    company = relationship("CRMCompany")
    creator = relationship("User")

    __table_args__ = (
        Index("idx_crm_research_org", "org_id"),
    )


class CRMChatSession(Base):
    __tablename__ = "crm_chat_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=True)
    session_type = Column(String(50), default="general")
    context = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = relationship("Org")
    user = relationship("User")

    __table_args__ = (
        Index("idx_crm_chat_org", "org_id"),
        Index("idx_crm_chat_user", "user_id"),
    )


class CRMChatMessage(Base):
    __tablename__ = "crm_chat_messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("crm_chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("CRMChatSession")

    __table_args__ = (
        Index("idx_crm_msg_session", "session_id"),
    )
