from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_user, require_org_membership
from app.models.models import Org, OrgMember, User, AuditLog
from app.schemas.schemas import OrgCreate, OrgResponse, OrgMemberCreate, OrgMemberResponse

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


@router.get("", response_model=list[OrgResponse])
def list_orgs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_ids = [m.org_id for m in user.memberships]
    return db.query(Org).filter(Org.id.in_(org_ids)).all()


@router.post("", response_model=OrgResponse)
def create_org(data: OrgCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = Org(name=data.name, org_type=data.org_type)
    db.add(org)
    db.flush()
    member = OrgMember(org_id=org.id, user_id=user.id, role="org_admin")
    db.add(member)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="org", entity_id=org.id))
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
def list_members(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_membership(user, org_id)
    members = db.query(OrgMember).filter(OrgMember.org_id == org_id).all()
    return [OrgMemberResponse(
        id=m.id, org_id=m.org_id, user_id=m.user_id, role=m.role.value,
        user_name=m.user.full_name, user_email=m.user.email
    ) for m in members]


@router.post("/{org_id}/members", response_model=OrgMemberResponse)
def add_member(org_id: str, data: OrgMemberCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_membership(user, org_id)
    existing = db.query(OrgMember).filter(OrgMember.org_id == org_id, OrgMember.user_id == data.user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already a member")
    member = OrgMember(org_id=org_id, user_id=data.user_id, role=data.role)
    db.add(member)
    db.add(AuditLog(user_id=user.id, action="add_member", entity_type="org", entity_id=org_id))
    db.commit()
    db.refresh(member)
    return OrgMemberResponse(
        id=member.id, org_id=member.org_id, user_id=member.user_id, role=member.role.value,
        user_name=member.user.full_name, user_email=member.user.email
    )
