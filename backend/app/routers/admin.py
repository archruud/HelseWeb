"""Admin router - user management, system stats, audit log."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models import User, Document, Hospital, AuditLog, Annotation, PrivateFile
from app.routers.auth import (
    get_current_user, require_permission, get_password_hash, _user_response, ROLE_PERMISSIONS
)

router = APIRouter()

ASSIGNABLE_ROLES = ["super_editor", "editor", "viewer"]


class UserCreateAdmin(BaseModel):
    username: str
    password: str
    full_name: str
    email: Optional[str] = None
    role: str = "viewer"

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class PasswordReset(BaseModel):
    new_password: str


@router.get("/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("admin"))):
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar()
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    annotation_count = (await db.execute(select(func.count(Annotation.id)))).scalar()
    private_count = (await db.execute(select(func.count(PrivateFile.id)))).scalar()
    return {
        "total_documents": doc_count,
        "total_users": user_count,
        "total_annotations": annotation_count,
        "total_private_files": private_count,
    }


@router.get("/roles")
async def list_roles(current_user: User = Depends(require_permission("manage_users"))):
    """Available roles an admin can assign, with their permissions."""
    return {
        "assignable_roles": ASSIGNABLE_ROLES,
        "permissions": {r: sorted(p) for r, p in ROLE_PERMISSIONS.items()},
    }


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("manage_users"))):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [{
        "id": str(u.id),
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "is_system_admin": bool(u.is_system_admin),
        "last_login": str(u.last_login) if u.last_login else None,
    } for u in users]


@router.post("/users")
async def create_user(data: UserCreateAdmin, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("manage_users"))):
    if data.role not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail=f"Ugyldig rolle. Tillatte: {', '.join(ASSIGNABLE_ROLES)}")
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Brukernavn er allerede i bruk")
    new_user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        full_name=data.full_name,
        email=data.email,
        role=data.role,
        is_active=True,
        is_system_admin=False,
        must_change_password=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return _user_response(new_user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("manage_users"))):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Bruker ikke funnet")
    if user.is_system_admin:
        raise HTTPException(status_code=403, detail="System-admin kan ikke endres")
    if data.role is not None:
        if data.role not in ASSIGNABLE_ROLES:
            raise HTTPException(status_code=400, detail="Ugyldig rolle")
        user.role = data.role
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.email is not None:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active
    await db.commit()
    return _user_response(user)


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, data: PasswordReset, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("manage_users"))):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Bruker ikke funnet")
    if user.is_system_admin:
        raise HTTPException(status_code=403, detail="System-admin passord endres kun via terminal")
    user.password_hash = get_password_hash(data.new_password)
    user.must_change_password = True
    await db.commit()
    return {"message": f"Passord tilbakestilt for {user.username}"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("manage_users"))):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Bruker ikke funnet")
    if user.is_system_admin:
        raise HTTPException(status_code=403, detail="System-admin kan ikke slettes")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Kan ikke slette deg selv")
    await db.delete(user)
    await db.commit()
    return {"message": "Bruker slettet"}


@router.get("/audit")
async def get_audit_log(limit: int = 50, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("admin"))):
    result = await db.execute(
        select(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [{
        "id": log.id,
        "user_name": user_name,
        "action": log.action,
        "resource_type": log.resource_type,
        "details": log.details,
        "created_at": str(log.created_at),
    } for log, user_name in rows]
