"""Documents router - CRUD, consistent search, tree view, threads, PDF."""
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text, desc
from pydantic import BaseModel
import uuid
import os
import shutil

from app.config import settings
from app.database import get_db
from app.models import Document, Hospital, User, JournalEntry
from app.routers.auth import get_current_user, user_permissions

router = APIRouter()


def can_see_psychiatric(user: User) -> bool:
    return "view_psychiatric" in user_permissions(user.role)


class DocumentResponse(BaseModel):
    id: str
    document_number: Optional[str]
    title: str
    document_type: Optional[str]
    category: str
    hospital_name: Optional[str]
    hospital_id: Optional[int]
    department: Optional[str]
    doctor_name: Optional[str]
    document_date: Optional[date]
    page_count: Optional[int]
    summary: Optional[str]
    thread_id: Optional[str]
    file_path: str


class SearchResult(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    grouped_by_department: dict = {}


@router.get("/tree")
async def get_document_tree(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Hierarchical tree: Year -> Month -> Hospital -> Documents."""
    query = select(Document, Hospital.name.label("hospital_name")).outerjoin(
        Hospital, Document.hospital_id == Hospital.id
    ).order_by(Document.document_date.desc())

    if not can_see_psychiatric(current_user):
        query = query.where(Document.category != "psychiatric")

    result = await db.execute(query)
    rows = result.all()

    month_names = ["Januar", "Februar", "Mars", "April", "Mai", "Juni",
                   "Juli", "August", "September", "Oktober", "November", "Desember"]
    tree = {}
    for doc, hospital_name in rows:
        if not doc.document_date:
            year, month = "Ukjent år", "Ukjent"
        else:
            year = str(doc.document_date.year)
            month = month_names[doc.document_date.month - 1]
        hosp = hospital_name or "Ukjent sykehus"
        tree.setdefault(year, {}).setdefault(month, {}).setdefault(hosp, []).append({
            "id": str(doc.id), "title": doc.title, "date": str(doc.document_date) if doc.document_date else None,
        })

    tree_nodes = []
    for year in sorted(tree.keys(), reverse=True):
        year_children = []
        # Keep month order chronological within a year
        for month in sorted(tree[year].keys(), key=lambda m: month_names.index(m) if m in month_names else 99):
            month_children = []
            for hospital in sorted(tree[year][month].keys()):
                docs = tree[year][month][hospital]
                hospital_children = [
                    {"id": d["id"], "label": f"{d['date']} - {d['title']}", "type": "document", "document_id": d["id"]}
                    for d in docs
                ]
                month_children.append({
                    "id": f"{year}-{month}-{hospital}", "label": hospital, "type": "hospital",
                    "children": hospital_children, "count": len(hospital_children),
                })
            year_children.append({"id": f"{year}-{month}", "label": month, "type": "month", "children": month_children})
        tree_nodes.append({
            "id": year, "label": year, "type": "year", "children": year_children,
            "count": sum(len(tree[year][m][h]) for m in tree[year] for h in tree[year][m]),
        })
    return tree_nodes


@router.get("/search", response_model=SearchResult)
async def search_documents(
    q: Optional[str] = None,
    hospital_id: Optional[int] = None,
    document_type: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    group_by_department: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Consistent full-text search using PostgreSQL norwegian tsvector.
    When filtering by hospital, returns ALL matching docs sorted by department + date.
    """
    filters = []

    # Full-text search via tsvector (consistent, ranked) with ILIKE fallback
    rank_order = None
    if q:
        ts_query = func.plainto_tsquery('norwegian', q)
        filters.append(
            or_(
                Document.search_vector.op('@@')(ts_query),
                Document.title.ilike(f"%{q}%"),
                Document.ocr_text.ilike(f"%{q}%"),
                Document.department.ilike(f"%{q}%"),
            )
        )
        rank_order = func.ts_rank(Document.search_vector, ts_query)

    if hospital_id:
        filters.append(Document.hospital_id == hospital_id)
    if document_type:
        filters.append(Document.document_type == document_type)
    if category:
        filters.append(Document.category == category)
    if department:
        filters.append(Document.department.ilike(f"%{department}%"))
    # Date filter only applies in document search when NOT filtering by hospital.
    # (Hospital filter should show ALL docs from that hospital regardless of date,
    #  since scanned docs may have scan-date not content-date. Use entries-search for date ranges.)
    if date_from and not hospital_id:
        filters.append(or_(Document.document_date >= date_from, Document.document_date.is_(None)))
    if date_to and not hospital_id:
        filters.append(or_(Document.document_date <= date_to, Document.document_date.is_(None)))

    if not can_see_psychiatric(current_user):
        filters.append(Document.category != "psychiatric")

    base = select(Document, Hospital.name.label("hospital_name")).outerjoin(
        Hospital, Document.hospital_id == Hospital.id
    )
    count_q = select(func.count(Document.id))
    if filters:
        base = base.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar()

    # Sorting: by relevance if text query, else by department then date.
    # When grouping by department (e.g. all docs from a hospital), sort dept + date.
    if hospital_id or group_by_department:
        base = base.order_by(Document.department.asc().nullslast(), Document.document_date.desc())
    elif rank_order is not None:
        base = base.order_by(desc(rank_order), Document.document_date.desc())
    else:
        base = base.order_by(Document.document_date.desc())

    base = base.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(base)).all()

    documents = []
    grouped: dict = {}
    for doc, hospital_name in rows:
        d = DocumentResponse(
            id=str(doc.id), document_number=doc.document_number, title=doc.title,
            document_type=doc.document_type, category=doc.category, hospital_name=hospital_name,
            hospital_id=doc.hospital_id, department=doc.department, doctor_name=doc.doctor_name,
            document_date=doc.document_date, page_count=doc.page_count, summary=doc.summary,
            thread_id=str(doc.thread_id) if doc.thread_id else None, file_path=doc.file_path,
        )
        documents.append(d)
        dept = doc.department or "Uten avdeling"
        grouped.setdefault(dept, []).append(d.id)

    return SearchResult(
        documents=documents, total=total, page=page, page_size=page_size,
        grouped_by_department=(grouped if (hospital_id or group_by_department) else {}),
    )


@router.get("/entries/search")
async def search_entries(
    q: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    hospital_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search dated journal entries - finds actual events by their real date
    (e.g. 1990-1995 finds entries from that period even inside big scanned documents)."""
    filters = []
    rank_order = None
    if q:
        ts_query = func.plainto_tsquery('norwegian', q)
        filters.append(or_(JournalEntry.search_vector.op('@@')(ts_query), JournalEntry.content.ilike(f"%{q}%")))
        rank_order = func.ts_rank(JournalEntry.search_vector, ts_query)
    if date_from:
        filters.append(JournalEntry.entry_date >= date_from)
    if date_to:
        filters.append(JournalEntry.entry_date <= date_to)
    if hospital_id:
        filters.append(JournalEntry.hospital_id == hospital_id)

    base = select(JournalEntry, Hospital.name.label("hn"), Document.title.label("doc_title")) \
        .outerjoin(Hospital, JournalEntry.hospital_id == Hospital.id) \
        .outerjoin(Document, JournalEntry.document_id == Document.id)
    count_q = select(func.count(JournalEntry.id))
    if filters:
        base = base.where(and_(*filters))
        count_q = count_q.where(and_(*filters))
    total = (await db.execute(count_q)).scalar()
    if rank_order is not None:
        base = base.order_by(desc(rank_order), JournalEntry.entry_date.asc())
    else:
        base = base.order_by(JournalEntry.entry_date.asc())
    base = base.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(base)).all()
    entries = [{
        "id": str(e.id), "document_id": str(e.document_id), "entry_date": str(e.entry_date) if e.entry_date else None,
        "heading": e.heading, "hospital_name": hn, "document_title": doc_title,
        "excerpt": (e.content or "")[:400],
    } for e, hn, doc_title in rows]
    return {"entries": entries, "total": total, "page": page, "page_size": page_size}


@router.get("/hospital-latest")
async def hospital_latest_dates(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Newest document date per hospital - so user knows if updates may be missing."""
    result = await db.execute(
        select(
            Hospital.id, Hospital.name,
            func.max(Document.document_date).label("latest"),
            func.count(Document.id).label("count"),
        ).outerjoin(Document, Document.hospital_id == Hospital.id)
        .group_by(Hospital.id, Hospital.name)
        .order_by(Hospital.name)
    )
    out = []
    for hid, name, latest, count in result.all():
        if count and count > 0:
            out.append({
                "hospital_id": hid, "hospital_name": name,
                "latest_document_date": str(latest) if latest else None,
                "document_count": count,
            })
    return out


@router.get("/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Document, Hospital.name.label("hospital_name"))
        .outerjoin(Hospital, Document.hospital_id == Hospital.id)
        .where(Document.id == uuid.UUID(document_id))
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Dokument ikke funnet")
    doc, hospital_name = row
    if doc.category == "psychiatric" and not can_see_psychiatric(current_user):
        raise HTTPException(status_code=403, detail="Ikke tilgang til psykiatriske dokumenter")
    return {
        "id": str(doc.id), "document_number": doc.document_number, "title": doc.title,
        "document_type": doc.document_type, "category": doc.category, "hospital_name": hospital_name,
        "hospital_id": doc.hospital_id, "department": doc.department, "doctor_name": doc.doctor_name,
        "doctor_approved_by": doc.doctor_approved_by,
        "document_date": str(doc.document_date) if doc.document_date else None,
        "created_date": str(doc.created_date) if doc.created_date else None,
        "page_count": doc.page_count, "ocr_text": doc.ocr_text, "summary": doc.summary,
        "diagnoses": doc.diagnoses, "procedures": doc.procedures, "keywords": doc.keywords,
        "thread_id": str(doc.thread_id) if doc.thread_id else None,
        "sender": doc.sender, "recipient": doc.recipient, "is_reply": doc.is_reply,
        "correspondence_key": doc.correspondence_key,
        "file_path": doc.file_path, "file_size_bytes": doc.file_size_bytes, "is_verified": doc.is_verified,
    }


@router.get("/{document_id}/pdf")
async def get_document_pdf(document_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the PDF file for a document by its ID (inline)."""
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc or not doc.file_path:
        raise HTTPException(status_code=404, detail="PDF ikke funnet")
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="PDF-fil mangler på disk")
    return FileResponse(doc.file_path, media_type="application/pdf", filename=os.path.basename(doc.file_path))


@router.get("/{document_id}/correspondence")
async def get_correspondence(document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return the full correspondence thread this document belongs to, chronologically."""
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument ikke funnet")

    key = doc.correspondence_key
    if not key:
        # No thread - return just this doc
        return {"correspondence_key": None, "documents": [await _doc_brief(db, doc)]}

    rows = await db.execute(
        select(Document, Hospital.name.label("hn")).outerjoin(Hospital, Document.hospital_id == Hospital.id)
        .where(Document.correspondence_key == key).order_by(Document.document_date.asc())
    )
    docs = []
    for d, hn in rows.all():
        docs.append({
            "id": str(d.id), "title": d.title, "document_type": d.document_type,
            "document_date": str(d.document_date) if d.document_date else None,
            "hospital_name": hn, "sender": d.sender, "recipient": d.recipient,
            "is_reply": d.is_reply, "summary": d.summary,
        })
    return {"correspondence_key": key, "documents": docs}


async def _doc_brief(db, doc):
    return {
        "id": str(doc.id), "title": doc.title, "document_type": doc.document_type,
        "document_date": str(doc.document_date) if doc.document_date else None,
        "sender": doc.sender, "recipient": doc.recipient, "summary": doc.summary,
    }


@router.get("/thread/{thread_id}")
async def get_thread_documents(thread_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Document, Hospital.name.label("hospital_name"))
        .outerjoin(Hospital, Document.hospital_id == Hospital.id)
        .where(Document.thread_id == uuid.UUID(thread_id))
        .order_by(Document.document_date.asc())
    )
    rows = result.all()
    return [{
        "id": str(doc.id), "title": doc.title, "document_type": doc.document_type,
        "hospital_name": hospital_name, "document_date": str(doc.document_date) if doc.document_date else None,
        "doctor_name": doc.doctor_name,
    } for doc, hospital_name in rows]
