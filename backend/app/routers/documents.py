"""Documents router - CRUD, search, tree view, upload."""
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, and_, or_
from pydantic import BaseModel
import uuid
import os
import shutil

from app.config import settings
from app.database import get_db
from app.models import Document, Hospital, User
from app.routers.auth import get_current_user

router = APIRouter()


# Pydantic schemas
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
    diagnoses: Optional[List[str]]
    keywords: Optional[List[str]]
    thread_id: Optional[str]
    has_annotations: bool = False
    annotation_count: int = 0
    file_path: str

class TreeNode(BaseModel):
    id: str
    label: str
    type: str  # year, month, hospital, document
    children: Optional[List["TreeNode"]] = None
    document_id: Optional[str] = None
    count: Optional[int] = None

class SearchResult(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


@router.get("/tree")
async def get_document_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get hierarchical tree: Year -> Month -> Hospital -> Documents."""
    # Get all documents with hospital info
    query = select(Document, Hospital.name.label("hospital_name")).outerjoin(
        Hospital, Document.hospital_id == Hospital.id
    ).order_by(Document.document_date.desc())
    
    # Filter by role permissions
    if current_user.role not in ("admin", "doctor"):
        query = query.where(Document.category != "psychiatric")
    
    result = await db.execute(query)
    rows = result.all()
    
    # Build tree structure
    tree = {}
    for doc, hospital_name in rows:
        if not doc.document_date:
            year = "Ukjent år"
            month = "Ukjent"
        else:
            year = str(doc.document_date.year)
            month_names = ["Januar", "Februar", "Mars", "April", "Mai", "Juni",
                          "Juli", "August", "September", "Oktober", "November", "Desember"]
            month = month_names[doc.document_date.month - 1]
        
        hosp = hospital_name or "Ukjent sykehus"
        
        if year not in tree:
            tree[year] = {}
        if month not in tree[year]:
            tree[year][month] = {}
        if hosp not in tree[year][month]:
            tree[year][month][hosp] = []
        
        tree[year][month][hosp].append({
            "id": str(doc.id),
            "title": doc.title,
            "type": doc.document_type,
            "date": str(doc.document_date) if doc.document_date else None
        })
    
    # Convert to tree nodes
    tree_nodes = []
    for year in sorted(tree.keys(), reverse=True):
        year_children = []
        for month in tree[year]:
            month_children = []
            for hospital in tree[year][month]:
                docs = tree[year][month][hospital]
                hospital_children = [
                    {"id": d["id"], "label": f"{d['date']} - {d['title']}", "type": "document", "document_id": d["id"]}
                    for d in docs
                ]
                month_children.append({
                    "id": f"{year}-{month}-{hospital}",
                    "label": hospital,
                    "type": "hospital",
                    "children": hospital_children,
                    "count": len(hospital_children)
                })
            year_children.append({
                "id": f"{year}-{month}",
                "label": month,
                "type": "month",
                "children": month_children
            })
        tree_nodes.append({
            "id": year,
            "label": year,
            "type": "year",
            "children": year_children,
            "count": sum(len(tree[year][m][h]) for m in tree[year] for h in tree[year][m])
        })
    
    return tree_nodes


@router.get("/search", response_model=SearchResult)
async def search_documents(
    q: Optional[str] = None,
    hospital_id: Optional[int] = None,
    document_type: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Full-text search with filters."""
    query = select(Document, Hospital.name.label("hospital_name")).outerjoin(
        Hospital, Document.hospital_id == Hospital.id
    )
    count_query = select(func.count(Document.id))
    
    # Apply filters
    filters = []
    if q:
        filters.append(
            or_(
                Document.ocr_text.ilike(f"%{q}%"),
                Document.title.ilike(f"%{q}%"),
                Document.doctor_name.ilike(f"%{q}%")
            )
        )
    if hospital_id:
        filters.append(Document.hospital_id == hospital_id)
    if document_type:
        filters.append(Document.document_type == document_type)
    if category:
        filters.append(Document.category == category)
    if date_from:
        filters.append(Document.document_date >= date_from)
    if date_to:
        filters.append(Document.document_date <= date_to)
    
    # Role-based filtering
    if current_user.role not in ("admin", "doctor", "psychologist"):
        filters.append(Document.category != "psychiatric")
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Paginate
    query = query.order_by(Document.document_date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()
    
    documents = []
    for doc, hospital_name in rows:
        documents.append(DocumentResponse(
            id=str(doc.id),
            document_number=doc.document_number,
            title=doc.title,
            document_type=doc.document_type,
            category=doc.category,
            hospital_name=hospital_name,
            hospital_id=doc.hospital_id,
            department=doc.department,
            doctor_name=doc.doctor_name,
            document_date=doc.document_date,
            page_count=doc.page_count,
            summary=doc.summary,
            diagnoses=doc.diagnoses,
            keywords=doc.keywords,
            thread_id=str(doc.thread_id) if doc.thread_id else None,
            file_path=doc.file_path
        ))
    
    return SearchResult(documents=documents, total=total, page=page, page_size=page_size)


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single document with full details."""
    result = await db.execute(
        select(Document, Hospital.name.label("hospital_name"))
        .outerjoin(Hospital, Document.hospital_id == Hospital.id)
        .where(Document.id == uuid.UUID(document_id))
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Dokument ikke funnet")
    
    doc, hospital_name = row
    
    # Check access
    if doc.category == "psychiatric" and current_user.role not in ("admin", "doctor", "psychologist"):
        raise HTTPException(status_code=403, detail="Ikke tilgang til psykiatriske dokumenter")
    
    return {
        "id": str(doc.id),
        "document_number": doc.document_number,
        "title": doc.title,
        "document_type": doc.document_type,
        "category": doc.category,
        "hospital_name": hospital_name,
        "hospital_id": doc.hospital_id,
        "department": doc.department,
        "doctor_name": doc.doctor_name,
        "doctor_approved_by": doc.doctor_approved_by,
        "document_date": str(doc.document_date) if doc.document_date else None,
        "created_date": str(doc.created_date) if doc.created_date else None,
        "page_count": doc.page_count,
        "ocr_text": doc.ocr_text,
        "summary": doc.summary,
        "diagnoses": doc.diagnoses,
        "procedures": doc.procedures,
        "keywords": doc.keywords,
        "thread_id": str(doc.thread_id) if doc.thread_id else None,
        "file_path": doc.file_path,
        "file_size_bytes": doc.file_size_bytes,
        "is_verified": doc.is_verified
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = "",
    hospital_id: Optional[int] = None,
    document_type: Optional[str] = None,
    document_date: Optional[str] = None,
    category: str = "somatic",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a new document (PDF)."""
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Kun administrator kan laste opp dokumenter")
    
    # Save file
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1] or ".pdf"
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{file_ext}")
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    file_size = os.path.getsize(file_path)
    
    # Parse date
    doc_date = None
    if document_date:
        try:
            doc_date = datetime.strptime(document_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    # Create document record
    doc = Document(
        title=title or file.filename,
        document_type=document_type,
        category=category,
        hospital_id=hospital_id,
        document_date=doc_date,
        file_path=file_path,
        file_size_bytes=file_size,
        uploaded_by=current_user.id
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    # TODO: Trigger async OCR and AI processing via Celery
    
    return {"id": str(doc.id), "message": "Dokument lastet opp", "file_path": file_path}


@router.get("/thread/{thread_id}")
async def get_thread_documents(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents in a thread (related documents chain)."""
    result = await db.execute(
        select(Document, Hospital.name.label("hospital_name"))
        .outerjoin(Hospital, Document.hospital_id == Hospital.id)
        .where(Document.thread_id == uuid.UUID(thread_id))
        .order_by(Document.document_date.asc())
    )
    rows = result.all()
    
    return [{
        "id": str(doc.id),
        "title": doc.title,
        "document_type": doc.document_type,
        "hospital_name": hospital_name,
        "document_date": str(doc.document_date) if doc.document_date else None,
        "doctor_name": doc.doctor_name
    } for doc, hospital_name in rows]
