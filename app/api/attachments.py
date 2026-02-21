import os
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import Attachment, Task, FieldEntry, User, Project
from app.schemas.schemas import AttachmentResponse

router = APIRouter(prefix="/api", tags=["attachments"])

UPLOAD_DIR = os.path.join("app", "static", "uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def secure_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\s\-.]', '', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename or "file"


def _save_file(task_id: str, upload: UploadFile, user: User, db: Session, field_entry_id: str = None) -> Attachment:
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '{upload.content_type}' not allowed. Accepted: jpeg, png, webp, pdf")

    content = upload.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

    safe_name = secure_filename(upload.filename or "file")
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"

    task_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    file_path = os.path.join(task_dir, unique_name)
    with open(file_path, "wb") as f:
        f.write(content)

    relative_url = f"/static/uploads/{task_id}/{unique_name}"

    attachment = Attachment(
        task_id=task_id,
        field_entry_id=field_entry_id,
        filename=safe_name,
        file_path=relative_url,
        file_type=upload.content_type,
        file_size=len(content),
        uploaded_by=user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def _attachment_response(a: Attachment) -> AttachmentResponse:
    return AttachmentResponse(
        id=a.id,
        filename=a.filename,
        file_path=a.file_path,
        file_type=a.file_type,
        file_size=a.file_size,
        created_at=a.created_at,
    )


@router.post("/tasks/{task_id}/attachments", response_model=list[AttachmentResponse])
async def upload_task_attachments(
    task_id: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    results = []
    for f in files:
        att = _save_file(task_id, f, user, db)
        results.append(_attachment_response(att))
    return results


@router.post("/field-entries/{entry_id}/attachments", response_model=list[AttachmentResponse])
async def upload_field_entry_attachments(
    entry_id: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(FieldEntry).filter(FieldEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Field entry not found")
    
    task = db.query(Task).filter(Task.id == entry.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    results = []
    for f in files:
        att = _save_file(entry.task_id, f, user, db, field_entry_id=entry_id)
        results.append(_attachment_response(att))
    return results


@router.get("/tasks/{task_id}/attachments", response_model=list[AttachmentResponse])
def list_task_attachments(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    attachments = (
        db.query(Attachment)
        .filter(Attachment.task_id == task_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )
    return [_attachment_response(a) for a in attachments]


@router.get("/field-entries/{entry_id}/attachments", response_model=list[AttachmentResponse])
def list_field_entry_attachments(
    entry_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(FieldEntry).filter(FieldEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Field entry not found")
    
    task = db.query(Task).filter(Task.id == entry.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    attachments = (
        db.query(Attachment)
        .filter(Attachment.field_entry_id == entry_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )
    return [_attachment_response(a) for a in attachments]


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    task = None
    if attachment.task_id:
        task = db.query(Task).filter(Task.id == attachment.task_id).first()
    elif attachment.field_entry_id:
        entry = db.query(FieldEntry).filter(FieldEntry.id == attachment.field_entry_id).first()
        if entry:
            task = db.query(Task).filter(Task.id == entry.task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found for attachment")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project, db)

    full_path = os.path.join("app", "static", attachment.file_path.lstrip("/static/"))
    if attachment.file_path.startswith("/static/uploads/"):
        full_path = os.path.join("app", attachment.file_path.lstrip("/"))
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except OSError:
        pass

    db.delete(attachment)
    db.commit()
    return {"ok": True}
