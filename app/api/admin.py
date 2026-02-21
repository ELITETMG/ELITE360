from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import uuid, json
from app.db.session import get_db
from app.core.auth import get_current_user, hash_password
from app.models.models import (User, UserProfile, OrgMember, Org, RoleName,
    OrgInvite, AuditLog, Project, Task, Crew, CrewMember)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ROLE_DESCRIPTIONS = {
    "super_admin": "Super Administrator",
    "org_admin": "Organization Admin",
    "pm": "Project Manager",
    "field_lead": "Field Lead",
    "crew_member": "Crew Member",
    "inspector": "Inspector",
    "finance": "Finance",
    "client_viewer": "Client Viewer",
}


def _get_membership(user: User, db: Session) -> OrgMember:
    membership = db.query(OrgMember).filter(OrgMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership found")
    return membership


def _require_admin(user: User, db: Session) -> OrgMember:
    membership = _get_membership(user, db)
    if membership.role not in (RoleName.ORG_ADMIN, RoleName.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")
    return membership


@router.get("/users")
def list_users(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org_id = membership.org_id

    members = db.query(OrgMember, User, UserProfile).join(
        User, OrgMember.user_id == User.id
    ).outerjoin(
        UserProfile, UserProfile.user_id == User.id
    ).filter(OrgMember.org_id == org_id).all()

    results = []
    for om, u, profile in members:
        profile_data = None
        if profile:
            profile_data = {
                "phone": profile.phone,
                "title": profile.title,
                "department": profile.department,
                "timezone": profile.timezone,
                "certifications": profile.certifications,
                "emergency_contact": profile.emergency_contact,
                "hire_date": profile.hire_date.isoformat() if profile.hire_date else None,
                "hourly_rate": profile.hourly_rate,
                "avatar_url": profile.avatar_url,
            }
        results.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "role": om.role.value if hasattr(om.role, 'value') else om.role,
            "profile": profile_data,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return results


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org_id = membership.org_id

    target_member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="User not found in organization")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    profile_data = None
    if profile:
        profile_data = {
            "phone": profile.phone,
            "title": profile.title,
            "department": profile.department,
            "timezone": profile.timezone,
            "certifications": profile.certifications,
            "emergency_contact": profile.emergency_contact,
            "hire_date": profile.hire_date.isoformat() if profile.hire_date else None,
            "hourly_rate": profile.hourly_rate,
            "avatar_url": profile.avatar_url,
        }

    all_memberships = db.query(OrgMember, Org).join(
        Org, OrgMember.org_id == Org.id
    ).filter(OrgMember.user_id == user_id).all()
    memberships_data = [{
        "org_id": om.org_id,
        "org_name": org.name,
        "role": om.role.value if hasattr(om.role, 'value') else om.role,
        "created_at": om.created_at.isoformat() if om.created_at else None,
    } for om, org in all_memberships]

    task_count = db.query(func.count(Task.id)).filter(Task.assigned_to == user_id).scalar() or 0
    audit_count = db.query(func.count(AuditLog.id)).filter(AuditLog.user_id == user_id).scalar() or 0

    return {
        "id": target_user.id,
        "email": target_user.email,
        "full_name": target_user.full_name,
        "is_active": target_user.is_active,
        "role": target_member.role.value if hasattr(target_member.role, 'value') else target_member.role,
        "profile": profile_data,
        "memberships": memberships_data,
        "activity_stats": {
            "assigned_tasks": task_count,
            "audit_entries": audit_count,
        },
        "created_at": target_user.created_at.isoformat() if target_user.created_at else None,
        "updated_at": target_user.updated_at.isoformat() if target_user.updated_at else None,
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org_id = membership.org_id

    target_member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="User not found in organization")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if "full_name" in data:
        target_user.full_name = data["full_name"]
    if "email" in data:
        existing = db.query(User).filter(User.email == data["email"], User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        target_user.email = data["email"]
    if "is_active" in data:
        target_user.is_active = data["is_active"]
    if "role" in data:
        try:
            target_member.role = RoleName(data["role"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {data['role']}")

    target_user.updated_at = datetime.utcnow()

    db.add(AuditLog(
        user_id=user.id, action="update_user", entity_type="user",
        entity_id=user_id, details=json.dumps(data)
    ))
    db.commit()
    db.refresh(target_user)

    return {
        "id": target_user.id,
        "email": target_user.email,
        "full_name": target_user.full_name,
        "is_active": target_user.is_active,
        "role": target_member.role.value if hasattr(target_member.role, 'value') else target_member.role,
        "updated_at": target_user.updated_at.isoformat() if target_user.updated_at else None,
    }


@router.post("/users")
def create_user(
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org_id = membership.org_id

    if not data.get("email") or not data.get("full_name") or not data.get("password"):
        raise HTTPException(status_code=400, detail="email, full_name, and password are required")

    existing = db.query(User).filter(User.email == data["email"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    role_str = data.get("role", "crew_member")
    try:
        role = RoleName(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role_str}")

    new_user = User(
        id=str(uuid.uuid4()),
        email=data["email"],
        full_name=data["full_name"],
        hashed_password=hash_password(data["password"]),
        is_active=True,
    )
    db.add(new_user)
    db.flush()

    org_member = OrgMember(
        id=str(uuid.uuid4()),
        org_id=org_id,
        user_id=new_user.id,
        role=role,
    )
    db.add(org_member)

    user_profile = UserProfile(
        id=str(uuid.uuid4()),
        user_id=new_user.id,
    )
    db.add(user_profile)

    db.add(AuditLog(
        user_id=user.id, action="create_user", entity_type="user",
        entity_id=new_user.id, details=json.dumps({"email": data["email"], "role": role_str})
    ))
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "is_active": new_user.is_active,
        "role": role_str,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
    }


@router.put("/users/{user_id}/profile")
def update_user_profile(
    user_id: str,
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org_id = membership.org_id

    target_member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="User not found in organization")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(id=str(uuid.uuid4()), user_id=user_id)
        db.add(profile)

    if "phone" in data:
        profile.phone = data["phone"]
    if "title" in data:
        profile.title = data["title"]
    if "department" in data:
        profile.department = data["department"]
    if "timezone" in data:
        profile.timezone = data["timezone"]
    if "certifications" in data:
        profile.certifications = data["certifications"]
    if "emergency_contact" in data:
        profile.emergency_contact = data["emergency_contact"]
    if "hire_date" in data:
        if data["hire_date"]:
            profile.hire_date = datetime.fromisoformat(data["hire_date"])
        else:
            profile.hire_date = None
    if "hourly_rate" in data:
        profile.hourly_rate = data["hourly_rate"]

    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)

    return {
        "user_id": profile.user_id,
        "phone": profile.phone,
        "title": profile.title,
        "department": profile.department,
        "timezone": profile.timezone,
        "certifications": profile.certifications,
        "emergency_contact": profile.emergency_contact,
        "hire_date": profile.hire_date.isoformat() if profile.hire_date else None,
        "hourly_rate": profile.hourly_rate,
        "avatar_url": profile.avatar_url,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@router.get("/users/{user_id}/profile")
def get_user_profile(
    user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org_id = membership.org_id

    target_member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="User not found in organization")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return {
            "user_id": user_id,
            "phone": None, "title": None, "department": None,
            "timezone": None, "certifications": None,
            "emergency_contact": None, "hire_date": None,
            "hourly_rate": None, "avatar_url": None,
        }

    return {
        "user_id": profile.user_id,
        "phone": profile.phone,
        "title": profile.title,
        "department": profile.department,
        "timezone": profile.timezone,
        "certifications": profile.certifications,
        "emergency_contact": profile.emergency_contact,
        "hire_date": profile.hire_date.isoformat() if profile.hire_date else None,
        "hourly_rate": profile.hourly_rate,
        "avatar_url": profile.avatar_url,
    }


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org_id = membership.org_id

    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    target_member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="User not found in organization")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.is_active = False
    target_user.updated_at = datetime.utcnow()

    db.add(AuditLog(
        user_id=user.id, action="deactivate_user", entity_type="user",
        entity_id=user_id
    ))
    db.commit()

    return {"ok": True, "message": f"User {target_user.email} has been deactivated"}


@router.get("/roles")
def list_roles(user: User = Depends(get_current_user)):
    return [
        {"role": role, "description": desc}
        for role, desc in ROLE_DESCRIPTIONS.items()
    ]


@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: str,
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org_id = membership.org_id

    if not data.get("role"):
        raise HTTPException(status_code=400, detail="role is required")

    target_member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="User not found in organization")

    try:
        target_member.role = RoleName(data["role"])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {data['role']}")

    db.add(AuditLog(
        user_id=user.id, action="change_role", entity_type="user",
        entity_id=user_id, details=json.dumps({"new_role": data["role"]})
    ))
    db.commit()

    return {
        "user_id": user_id,
        "role": target_member.role.value if hasattr(target_member.role, 'value') else target_member.role,
    }


@router.get("/org")
def get_org(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org = db.query(Org).filter(Org.id == membership.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member_count = db.query(func.count(OrgMember.id)).filter(
        OrgMember.org_id == org.id
    ).scalar() or 0

    project_count = db.query(func.count(Project.id)).filter(
        Project.executing_org_id == org.id
    ).scalar() or 0

    return {
        "id": org.id,
        "name": org.name,
        "org_type": org.org_type.value if hasattr(org.org_type, 'value') else org.org_type,
        "member_count": member_count,
        "project_count": project_count,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
    }


@router.put("/org")
def update_org(
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org = db.query(Org).filter(Org.id == membership.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if "name" in data:
        org.name = data["name"]

    org.updated_at = datetime.utcnow()

    db.add(AuditLog(
        user_id=user.id, action="update_org", entity_type="org",
        entity_id=org.id, details=json.dumps(data)
    ))
    db.commit()
    db.refresh(org)

    return {
        "id": org.id,
        "name": org.name,
        "org_type": org.org_type.value if hasattr(org.org_type, 'value') else org.org_type,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
    }


@router.get("/audit-log")
def get_audit_log(
    limit: int = Query(100, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org_id = membership.org_id

    org_user_ids = db.query(OrgMember.user_id).filter(OrgMember.org_id == org_id).subquery()

    entries = db.query(AuditLog, User).outerjoin(
        User, AuditLog.user_id == User.id
    ).filter(
        AuditLog.user_id.in_(org_user_ids)
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()

    return [{
        "id": entry.id,
        "user_id": entry.user_id,
        "user_name": u.full_name if u else None,
        "user_email": u.email if u else None,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "details": entry.details,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    } for entry, u in entries]


@router.get("/stats")
def get_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org_id = membership.org_id

    org_user_ids = db.query(OrgMember.user_id).filter(OrgMember.org_id == org_id)

    total_users = db.query(func.count(User.id)).filter(
        User.id.in_(org_user_ids)
    ).scalar() or 0

    active_users = db.query(func.count(User.id)).filter(
        User.id.in_(org_user_ids),
        User.is_active == True
    ).scalar() or 0

    role_counts = db.query(
        OrgMember.role, func.count(OrgMember.id)
    ).filter(OrgMember.org_id == org_id).group_by(OrgMember.role).all()

    users_by_role = {
        (r.value if hasattr(r, 'value') else r): c
        for r, c in role_counts
    }

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_signups = db.query(func.count(User.id)).filter(
        User.id.in_(org_user_ids),
        User.created_at >= seven_days_ago
    ).scalar() or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "users_by_role": users_by_role,
        "recent_signups": recent_signups,
    }


@router.post("/invites")
def create_invite(
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _require_admin(user, db)
    org_id = membership.org_id

    if not data.get("email"):
        raise HTTPException(status_code=400, detail="email is required")

    role_str = data.get("role", "crew_member")
    try:
        role = RoleName(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role_str}")

    existing = db.query(OrgInvite).filter(
        OrgInvite.org_id == org_id,
        OrgInvite.email == data["email"],
        OrgInvite.accepted == False,
        OrgInvite.expires_at > datetime.utcnow()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An active invite already exists for this email")

    invite = OrgInvite(
        id=str(uuid.uuid4()),
        org_id=org_id,
        email=data["email"],
        role=role,
        invited_by=user.id,
        token=str(uuid.uuid4()),
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)

    db.add(AuditLog(
        user_id=user.id, action="create_invite", entity_type="invite",
        entity_id=invite.id, details=json.dumps({"email": data["email"], "role": role_str})
    ))
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role.value if hasattr(invite.role, 'value') else invite.role,
        "token": invite.token,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
    }


@router.get("/invites")
def list_invites(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = _get_membership(user, db)
    org_id = membership.org_id

    invites = db.query(OrgInvite, User).outerjoin(
        User, OrgInvite.invited_by == User.id
    ).filter(
        OrgInvite.org_id == org_id,
        OrgInvite.accepted == False,
        OrgInvite.expires_at > datetime.utcnow()
    ).order_by(OrgInvite.created_at.desc()).all()

    return [{
        "id": inv.id,
        "email": inv.email,
        "role": inv.role.value if hasattr(inv.role, 'value') else inv.role,
        "token": inv.token,
        "invited_by": inv.invited_by,
        "invited_by_name": u.full_name if u else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    } for inv, u in invites]
