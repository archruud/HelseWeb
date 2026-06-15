"""Annotations router - patient notes on documents."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models import Annotation, User
from app.routers.auth import get_current_user

router = APIRouter()

class AnnotationCreate(BaseModel):
    document_id: str
    content: str
    annotation_type: str = "note"
    page_number: Optional[int] = None
    visibility: str = "all"

class AnnotationResponse(BaseModel):
    id: str
    document_id: str
    content: str
    annotation_type: str
    page_number: Optional[int]
    visibility: str
    user_name: str
    created_at: str

@router.get("/document/{document_id}")
async def get_annotations(document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Annotation, User.full_name)
        .join(User, Annotation.user_id == User.id)
        .where(Annotation.document_id == uuid.UUID(document_id))
        .order_by(Annotation.created_at.desc())
    )
    rows = result.all()
    
    annotations = []
    for ann, user_name in rows:
        # Check visibility
        if ann.visibility == "admin_only" and current_user.role != "admin":
            continue
        if ann.visibility == "doctors_only" and current_user.role not in ("admin", "doctor"):
            continue
        annotations.append(AnnotationResponse(
            id=str(ann.id),
            document_id=str(ann.document_id),
            content=ann.content,
            annotation_type=ann.annotation_type,
            page_number=ann.page_number,
            visibility=ann.visibility,
            user_name=user_name,
            created_at=str(ann.created_at)
        ))
    return annotations

@router.post("/", response_model=AnnotationResponse)
async def create_annotation(data: AnnotationCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "doctor", "psychologist"):
        raise HTTPException(status_code=403, detail="Ikke tilgang til å legge til notater")
    
    ann = Annotation(
        document_id=uuid.UUID(data.document_id),
        user_id=current_user.id,
        content=data.content,
        annotation_type=data.annotation_type,
        page_number=data.page_number,
        visibility=data.visibility
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    
    return AnnotationResponse(
        id=str(ann.id),
        document_id=str(ann.document_id),
        content=ann.content,
        annotation_type=ann.annotation_type,
        page_number=ann.page_number,
        visibility=ann.visibility,
        user_name=current_user.full_name,
        created_at=str(ann.created_at)
    )

@router.delete("/{annotation_id}")
async def delete_annotation(annotation_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Annotation).where(Annotation.id == uuid.UUID(annotation_id)))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Notat ikke funnet")
    if ann.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Kan kun slette egne notater")
    await db.delete(ann)
    await db.commit()
    return {"message": "Notat slettet"}
