import hashlib
import secrets
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.db.session import get_db
from app.models.models import User, OrgMember

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${h.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split('$', 1)
        check = hashlib.pbkdf2_hmac('sha256', plain.encode(), salt.encode(), 100000)
        return check.hex() == h
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User | None:
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_user_org_ids(user: User) -> list[str]:
    return [m.org_id for m in user.memberships]


def get_user_role_in_org(user_id: str, org_id: str, db: Session) -> str | None:
    member = db.query(OrgMember).filter(
        OrgMember.user_id == user_id,
        OrgMember.org_id == org_id
    ).first()
    return member.role.value if member else None


def require_org_membership(user: User, org_id: str):
    org_ids = get_user_org_ids(user)
    if org_id not in org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")


def require_project_access(user: User, project, db: Session = None):
    from app.models.models import Project
    org_ids = get_user_org_ids(user)
    if project.executing_org_id not in org_ids and (project.owner_org_id is None or project.owner_org_id not in org_ids):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this project")


def require_role(allowed_roles: list[str]):
    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        for membership in user.memberships:
            if membership.role.value in allowed_roles:
                return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return dependency
