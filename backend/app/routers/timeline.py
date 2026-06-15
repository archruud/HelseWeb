"""Timeline router - key events visualization."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.database import get_db
from app.models import TimelineEvent, Hospital, User
from app.routers.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_timeline(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    event_type: Optional[str] = None,
    hospital_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(TimelineEvent, Hospital.name.label("hospital_name")).outerjoin(
        Hospital, TimelineEvent.hospital_id == Hospital.id
    )
    
    filters = []
    if date_from:
        filters.append(TimelineEvent.event_date >= date_from)
    if date_to:
        filters.append(TimelineEvent.event_date <= date_to)
    if event_type:
        filters.append(TimelineEvent.event_type == event_type)
    if hospital_id:
        filters.append(TimelineEvent.hospital_id == hospital_id)
    
    if filters:
        query = query.where(and_(*filters))
    
    query = query.order_by(TimelineEvent.event_date.desc())
    result = await db.execute(query)
    rows = result.all()
    
    return [{
        "id": str(e.id),
        "title": e.title,
        "description": e.description,
        "event_date": str(e.event_date),
        "end_date": str(e.end_date) if e.end_date else None,
        "event_type": e.event_type,
        "severity": e.severity,
        "hospital_name": hospital_name,
        "document_id": str(e.document_id) if e.document_id else None
    } for e, hospital_name in rows]

@router.post("/")
async def create_timeline_event(
    title: str,
    event_date: date,
    event_type: str = "milestone",
    severity: str = "normal",
    description: Optional[str] = None,
    hospital_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Kun admin kan opprette tidslinjehendelser")
    
    event = TimelineEvent(
        title=title,
        description=description,
        event_date=event_date,
        event_type=event_type,
        severity=severity,
        hospital_id=hospital_id
    )
    db.add(event)
    await db.commit()
    return {"id": str(event.id), "message": "Hendelse opprettet"}
