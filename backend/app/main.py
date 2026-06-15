"""
Helsejournal PHR - Personal Health Record System
Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import engine, Base
from app.routers import auth, documents, hospitals, annotations, private_files, timeline, ai_assistant, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title="Helsejournal PHR",
    description="Personlig Helsejournal - Document Management System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (uploaded documents)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.PRIVATE_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=settings.UPLOAD_DIR), name="files")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(hospitals.router, prefix="/api/hospitals", tags=["Hospitals"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["Annotations"])
app.include_router(private_files.router, prefix="/api/private", tags=["Private Files"])
app.include_router(timeline.router, prefix="/api/timeline", tags=["Timeline"])
app.include_router(ai_assistant.router, prefix="/api/ai", tags=["AI Assistant"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administration"])

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
