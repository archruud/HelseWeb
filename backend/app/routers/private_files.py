"""Private files router - patient's own audio, transcripts, etc."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel
import uuid, os, shutil

from app.config import settings
from app.database import get_db
from app.models import PrivateFile, User
from app.routers.auth import get_current_user, require_role

router = APIRouter()

@router.get("/")
async def list_private_files(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin",):
        # Check if user has specific permission
        result = await db.execute(
            select(PrivateFile).where(PrivateFile.allowed_roles.contains([current_user.role]))
        )
    else:
        result = await db.execute(select(PrivateFile).order_by(PrivateFile.created_at.desc()))
    
    files = result.scalars().all()
    return [{
        "id": str(f.id),
        "title": f.title,
        "description": f.description,
        "file_type": f.file_type,
        "duration_seconds": f.duration_seconds,
        "related_date": str(f.related_date) if f.related_date else None,
        "has_transcript": bool(f.transcript),
        "created_at": str(f.created_at)
    } for f in files]

@router.post("/upload")
async def upload_private_file(
    file: UploadFile = File(...),
    title: str = "",
    file_type: str = "document",
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(settings.PRIVATE_DIR, f"{file_id}{file_ext}")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    pf = PrivateFile(
        title=title or file.filename,
        description=description,
        file_type=file_type,
        file_path=file_path,
        file_size_bytes=os.path.getsize(file_path),
        uploaded_by=current_user.id
    )
    db.add(pf)
    await db.commit()
    return {"id": str(pf.id), "message": "Fil lastet opp"}
