"""Hospitals router."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import Hospital, Document, User
from app.routers.auth import get_current_user, user_permissions

router = APIRouter()

@router.get("/")
async def list_hospitals(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Hospital, func.count(Document.id).label("doc_count"))
        .outerjoin(Document, Document.hospital_id == Hospital.id)
        .group_by(Hospital.id)
        .order_by(Hospital.name)
    )
    rows = result.all()
    return [{
        "id": h.id,
        "name": h.name,
        "short_name": h.short_name,
        "city": h.city,
        "is_active": h.is_active,
        "parent_organization": h.parent_organization,
        "document_count": count
    } for h, count in rows]
