"""Admin router - user management, system stats, audit log."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import User, Document, Hospital, AuditLog, Annotation, PrivateFile
from app.routers.auth import get_current_user, require_role

router = APIRouter()

@router.get("/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar()
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    annotation_count = (await db.execute(select(func.count(Annotation.id)))).scalar()
    private_count = (await db.execute(select(func.count(PrivateFile.id)))).scalar()
    
    return {
        "total_documents": doc_count,
        "total_users": user_count,
        "total_annotations": annotation_count,
        "total_private_files": private_count
    }

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [{
        "id": str(u.id),
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "last_login": str(u.last_login) if u.last_login else None
    } for u in users]

@router.get("/audit")
async def get_audit_log(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
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
        "created_at": str(log.created_at)
    } for log, user_name in rows]
