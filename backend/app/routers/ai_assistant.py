"""AI Assistant router - RAG-based Q&A over medical records."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import httpx
import uuid

from app.config import settings
from app.database import get_db
from app.models import Document, AuditLog, User
from app.routers.auth import get_current_user

router = APIRouter()


class AIQuery(BaseModel):
    question: str
    context_filter: Optional[str] = None  # hospital, date range, etc.

class AIResponse(BaseModel):
    answer: str
    source_documents: List[dict]
    model_used: str


async def query_ollama(prompt: str, context: str) -> str:
    """Send query to local Ollama instance."""
    system_prompt = """Du er en medisinsk forskningsassistent som hjelper med å finne informasjon i pasientjournaler.
Du skal ALLTID oppgi hvilke dokumenter du baserer svaret på.
Du skal ALDRI stille diagnoser eller gi medisinske råd.
Du skal svare på norsk.
Hvis du ikke finner relevant informasjon, si det tydelig."""
    
    full_prompt = f"""Basert på følgende journalutdrag, svar på spørsmålet.

JOURNALUTDRAG:
{context}

SPØRSMÅL: {prompt}

SVAR (oppgi alltid kilde-dokumenter):"""
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 2000}
                }
            )
            if response.status_code == 200:
                return response.json().get("response", "Ingen respons fra AI-modellen.")
            else:
                return f"Feil ved kontakt med AI-modell: {response.status_code}"
    except Exception as e:
        return f"Kunne ikke koble til AI-tjenesten: {str(e)}"


@router.post("/query", response_model=AIResponse)
async def ai_query(
    query: AIQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ask the AI a question about the medical records."""
    if current_user.role not in ("admin", "doctor", "specialist"):
        raise HTTPException(status_code=403, detail="AI-søk krever lege- eller spesialist-tilgang")
    
    # Simple keyword-based retrieval (will be replaced with vector search)
    # Search for relevant documents
    search_terms = query.question.split()[:5]  # Use first 5 words as search
    
    results = await db.execute(
        select(Document)
        .where(Document.ocr_text.ilike(f"%{search_terms[0]}%"))
        .limit(5)
    )
    relevant_docs = results.scalars().all()
    
    # Build context from relevant documents
    context_parts = []
    source_docs = []
    for doc in relevant_docs:
        text_snippet = (doc.ocr_text or "")[:2000]
        context_parts.append(f"[Dokument: {doc.title}, Dato: {doc.document_date}]\n{text_snippet}")
        source_docs.append({
            "id": str(doc.id),
            "title": doc.title,
            "date": str(doc.document_date) if doc.document_date else None,
            "document_type": doc.document_type
        })
    
    context = "\n\n---\n\n".join(context_parts) if context_parts else "Ingen relevante dokumenter funnet."
    
    # Query the LLM
    answer = await query_ollama(query.question, context)
    
    # Log the query
    log = AuditLog(
        user_id=current_user.id,
        action="ai_query",
        resource_type="ai",
        details={"question": query.question, "sources": len(source_docs)}
    )
    db.add(log)
    await db.commit()
    
    return AIResponse(
        answer=answer,
        source_documents=source_docs,
        model_used=settings.OLLAMA_MODEL
    )


@router.get("/status")
async def ai_status():
    """Check if AI service (Ollama) is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return {
                    "status": "online",
                    "models": [m["name"] for m in models],
                    "configured_model": settings.OLLAMA_MODEL
                }
    except Exception:
        pass
    
    return {"status": "offline", "models": [], "configured_model": settings.OLLAMA_MODEL}
