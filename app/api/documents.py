import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_project_access
from app.models.models import Document, DocumentVersion, Project, User, Activity
from app.schemas.schemas import DocumentCreate, DocumentResponse, DocumentVersionResponse

router = APIRouter(prefix="/api", tags=["documents"])

UPLOAD_DIR = "app/static/uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def doc_to_response(doc, db):
    uploader = db.query(User).filter(User.id == doc.uploaded_by).first()
    locker = db.query(User).filter(User.id == doc.locked_by).first() if doc.locked_by else None
    return DocumentResponse(
        id=doc.id, project_id=doc.project_id, name=doc.name,
        description=doc.description, category=doc.category,
        current_version=doc.current_version, file_type=doc.file_type,
        file_size=doc.file_size, uploaded_by=doc.uploaded_by,
        uploader_name=uploader.full_name if uploader else None,
        locked_by=doc.locked_by,
        locker_name=locker.full_name if locker else None,
        locked_at=doc.locked_at,
        created_at=doc.created_at, updated_at=doc.updated_at
    )

@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    project_id: str,
    category: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    q = db.query(Document).filter(Document.project_id == project_id)
    if category:
        q = q.filter(Document.category == category)
    docs = q.order_by(Document.updated_at.desc()).all()
    return [doc_to_response(d, db) for d in docs]

@router.post("/projects/{project_id}/documents", response_model=DocumentResponse, status_code=201)
def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    category: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(user, project)
    
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    
    import uuid
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ''
    stored_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, stored_name)
    
    content = file.file.read()
    with open(file_path, 'wb') as f:
        f.write(content)
    
    doc = Document(
        project_id=project_id,
        name=name or file.filename or "Untitled",
        description=description,
        category=category,
        file_path=file_path,
        file_type=file.content_type,
        file_size=len(content),
        uploaded_by=user.id,
        current_version=1
    )
    db.add(doc)
    db.flush()
    
    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path=file_path,
        file_size=len(content),
        change_notes="Initial upload",
        uploaded_by=user.id
    )
    db.add(version)
    
    activity = Activity(
        project_id=project_id, user_id=user.id,
        action="document_uploaded", entity_type="document",
        entity_id=doc.id, entity_name=doc.name
    )
    db.add(activity)
    db.commit()
    db.refresh(doc)
    return doc_to_response(doc, db)

@router.post("/documents/{document_id}/versions", response_model=DocumentVersionResponse, status_code=201)
def upload_new_version(
    document_id: str,
    file: UploadFile = File(...),
    change_notes: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    project = db.query(Project).filter(Project.id == doc.project_id).first()
    require_project_access(user, project)
    
    if doc.locked_by and doc.locked_by != user.id:
        locker = db.query(User).filter(User.id == doc.locked_by).first()
        raise HTTPException(status_code=409, detail=f"Document is locked by {locker.full_name if locker else 'another user'}")
    
    import uuid
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ''
    stored_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, stored_name)
    
    content = file.file.read()
    with open(file_path, 'wb') as f:
        f.write(content)
    
    new_version = doc.current_version + 1
    version = DocumentVersion(
        document_id=doc.id,
        version_number=new_version,
        file_path=file_path,
        file_size=len(content),
        change_notes=change_notes,
        uploaded_by=user.id
    )
    db.add(version)
    
    doc.current_version = new_version
    doc.file_path = file_path
    doc.file_size = len(content)
    doc.file_type = file.content_type
    doc.updated_at = datetime.utcnow()
    if doc.locked_by == user.id:
        doc.locked_by = None
        doc.locked_at = None
    
    activity = Activity(
        project_id=doc.project_id, user_id=user.id,
        action="document_version_uploaded", entity_type="document",
        entity_id=doc.id, entity_name=f"{doc.name} v{new_version}"
    )
    db.add(activity)
    db.commit()
    db.refresh(version)
    
    uploader = db.query(User).filter(User.id == version.uploaded_by).first()
    return DocumentVersionResponse(
        id=version.id, document_id=version.document_id,
        version_number=version.version_number, file_size=version.file_size,
        change_notes=version.change_notes, uploaded_by=version.uploaded_by,
        uploader_name=uploader.full_name if uploader else None,
        created_at=version.created_at
    )

@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionResponse])
def list_versions(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    project = db.query(Project).filter(Project.id == doc.project_id).first()
    require_project_access(user, project)
    
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id
    ).order_by(DocumentVersion.version_number.desc()).all()
    
    result = []
    for v in versions:
        uploader = db.query(User).filter(User.id == v.uploaded_by).first()
        result.append(DocumentVersionResponse(
            id=v.id, document_id=v.document_id,
            version_number=v.version_number, file_size=v.file_size,
            change_notes=v.change_notes, uploaded_by=v.uploaded_by,
            uploader_name=uploader.full_name if uploader else None,
            created_at=v.created_at
        ))
    return result

@router.get("/documents/{document_id}/download")
def download_document(
    document_id: str,
    version: int = Query(None),
    token: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    project = db.query(Project).filter(Project.id == doc.project_id).first()
    require_project_access(user, project)
    
    if version:
        ver = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version
        ).first()
        if not ver:
            raise HTTPException(status_code=404, detail="Version not found")
        file_path = ver.file_path
    else:
        file_path = doc.file_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(file_path, filename=doc.name, media_type=doc.file_type or "application/octet-stream")

@router.post("/documents/{document_id}/lock")
def lock_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    project = db.query(Project).filter(Project.id == doc.project_id).first()
    require_project_access(user, project)
    
    if doc.locked_by and doc.locked_by != user.id:
        locker = db.query(User).filter(User.id == doc.locked_by).first()
        raise HTTPException(status_code=409, detail=f"Already locked by {locker.full_name if locker else 'another user'}")
    
    doc.locked_by = user.id
    doc.locked_at = datetime.utcnow()
    db.commit()
    return {"message": "Document locked", "locked_by": user.full_name}

@router.post("/documents/{document_id}/unlock")
def unlock_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    project = db.query(Project).filter(Project.id == doc.project_id).first()
    require_project_access(user, project)
    
    if doc.locked_by and doc.locked_by != user.id:
        from app.models.models import OrgMember, RoleName
        membership = db.query(OrgMember).filter(
            OrgMember.user_id == user.id,
            OrgMember.org_id == project.executing_org_id,
            OrgMember.role.in_([RoleName.ORG_ADMIN, RoleName.PM])
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Only admins/PMs can unlock documents locked by others")
    
    doc.locked_by = None
    doc.locked_at = None
    db.commit()
    return {"message": "Document unlocked"}

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    project = db.query(Project).filter(Project.id == doc.project_id).first()
    require_project_access(user, project)
    
    versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == document_id).all()
    for v in versions:
        if os.path.exists(v.file_path):
            try:
                os.remove(v.file_path)
            except OSError:
                pass
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass
    
    db.delete(doc)
    db.commit()
