"""Timeline router - key events, with auto-generation from documents."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from pydantic import BaseModel

from app.database import get_db
from app.models import TimelineEvent, Hospital, Document, User, JournalEntry
from app.routers.auth import get_current_user, require_permission

router = APIRouter()


@router.get("/")
async def get_timeline(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    event_type: Optional[str] = None,
    hospital_id: Optional[int] = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    query = query.order_by(TimelineEvent.event_date.desc()).limit(limit)
    rows = (await db.execute(query)).all()
    return [{
        "id": str(e.id), "title": e.title, "description": e.description,
        "event_date": str(e.event_date), "end_date": str(e.end_date) if e.end_date else None,
        "event_type": e.event_type, "severity": e.severity, "hospital_name": hospital_name,
        "document_id": str(e.document_id) if e.document_id else None,
        "auto_generated": e.auto_generated,
    } for e, hospital_name in rows]


class EventCreate(BaseModel):
    title: str
    event_date: date
    event_type: str = "milestone"
    severity: str = "normal"
    description: Optional[str] = None
    hospital_id: Optional[int] = None


@router.post("/")
async def create_timeline_event(data: EventCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "super_editor", "editor"):
        raise HTTPException(status_code=403, detail="Ikke tilgang til å opprette hendelser")
    event = TimelineEvent(
        title=data.title, description=data.description, event_date=data.event_date,
        event_type=data.event_type, severity=data.severity, hospital_id=data.hospital_id,
    )
    db.add(event)
    await db.commit()
    return {"id": str(event.id), "message": "Hendelse opprettet"}


@router.delete("/{event_id}")
async def delete_event(event_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("admin"))):
    import uuid
    result = await db.execute(select(TimelineEvent).where(TimelineEvent.id == uuid.UUID(event_id)))
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Hendelse ikke funnet")
    await db.delete(ev)
    await db.commit()
    return {"message": "Hendelse slettet"}


# Keywords that indicate significant events, with severity + type
EVENT_RULES = [
    ("intravenøs ernæring", "critical", "innleggelse", "Intravenøs ernæring"),
    ("parenteral ernæring", "critical", "innleggelse", "Parenteral ernæring"),
    ("pseudo-obstruksjon", "critical", "diagnose", "Pseudo-obstruksjon"),
    ("pseudoobstruksjon", "critical", "diagnose", "Pseudo-obstruksjon"),
    ("operasjon", "important", "operasjon", "Operasjon"),
    ("operasjonsbeskrivelse", "important", "operasjon", "Operasjon"),
    ("innlagt", "normal", "innleggelse", "Innleggelse"),
    ("epikrise", "normal", "innleggelse", "Innleggelse/epikrise"),
    ("suicid", "critical", "hendelse", "Kritisk psykisk hendelse"),
    ("fundoplicatio", "important", "operasjon", "Fundoplicatio"),
    ("pancreas divisum", "important", "diagnose", "Pancreas divisum"),
    ("parathyreoidea", "important", "operasjon", "Parathyreoidea"),
]


@router.post("/auto-generate")
async def auto_generate_timeline(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission("admin"))):
    """Scan documents and auto-create timeline events from key clinical keywords.
    Removes previous auto-generated events first to avoid duplicates.
    """
    # Remove existing auto-generated events
    await db.execute(delete(TimelineEvent).where(TimelineEvent.auto_generated == True))

    # Use DATED journal entries (real dates inside documents) when available
    rows = (await db.execute(
        select(JournalEntry, Hospital.name.label("hn")).outerjoin(Hospital, JournalEntry.hospital_id == Hospital.id)
        .where(JournalEntry.entry_date.isnot(None))
        .order_by(JournalEntry.entry_date.asc())
    )).all()

    created = 0
    seen = set()  # (date, type) to limit noise
    for entry, hn in rows:
        text_l = ((entry.heading or "") + " " + (entry.content or "")[:2000]).lower()
        for kw, severity, etype, label in EVENT_RULES:
            if kw in text_l:
                key = (str(entry.entry_date), etype)
                if key in seen:
                    continue
                seen.add(key)
                ev = TimelineEvent(
                    title=f"{label}",
                    description=f"{(entry.heading or '')[:80]} ({hn or 'ukjent sykehus'})",
                    event_date=entry.entry_date,
                    event_type=etype, severity=severity,
                    hospital_id=entry.hospital_id, document_id=entry.document_id,
                    auto_generated=True,
                )
                db.add(ev)
                created += 1
                break
    await db.commit()
    return {"message": f"Tidslinje generert: {created} hendelser opprettet"}
