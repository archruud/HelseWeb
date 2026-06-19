"""AI Assistant router - RAG-based Q&A over medical records with citations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from pydantic import BaseModel
from typing import Optional, List
import httpx
import uuid

from app.config import settings
from app.database import get_db
from app.models import Document, Hospital, AuditLog, User
from app.routers.auth import get_current_user, user_permissions

router = APIRouter()


class AIQuery(BaseModel):
    question: str


class AIResponse(BaseModel):
    answer: str
    source_documents: List[dict]
    model_used: str


SYSTEM_PROMPT = """Du er en medisinsk forskningsassistent for pasienten Terje Johan Ruud.
Du hjelper leger og spesialister med å finne informasjon i hans omfattende journaler.

VIKTIGE REGLER:
- Du skal ALLTID oppgi hvilke dokumenter du baserer svaret på (tittel + dato + sykehus).
- Du skal ALDRI stille diagnoser eller gi behandlingsråd - kun gjengi og oppsummere det som står i journalene.
- Du skal svare på norsk, presist og strukturert.
- Hvis informasjon mangler i utdragene, si det tydelig.
- Når du ser en korrespondanse (henvisning og svar), beskriv sammenhengen.
- Vær spesielt oppmerksom på forhold relevant for CIPO (kronisk intestinal pseudo-obstruksjon):
  tarmmotilitet, pseudo-obstruksjon, intravenøs ernæring, langvarige magesmerter, pankreas."""


async def retrieve_relevant_docs(db: AsyncSession, question: str, limit: int = 8):
    """Retrieve relevant documents using PostgreSQL full-text search (ts_rank)."""
    ts_query = func.plainto_tsquery('norwegian', question)
    stmt = (
        select(Document, Hospital.name.label("hn"), func.ts_rank(Document.search_vector, ts_query).label("rank"))
        .outerjoin(Hospital, Document.hospital_id == Hospital.id)
        .where(Document.search_vector.op('@@')(ts_query))
        .order_by(desc("rank"))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        # Fallback: keyword ILIKE on first significant words
        words = [w for w in question.split() if len(w) > 3][:3]
        if words:
            conds = [Document.ocr_text.ilike(f"%{w}%") for w in words]
            stmt2 = (
                select(Document, Hospital.name.label("hn"))
                .outerjoin(Hospital, Document.hospital_id == Hospital.id)
                .where(or_(*conds)).order_by(Document.document_date.desc()).limit(limit)
            )
            rows = [(d, hn, 0.0) for d, hn in (await db.execute(stmt2)).all()]
    return rows


async def query_ollama(question: str, context: str) -> str:
    full_prompt = f"""Basert på følgende journalutdrag, svar på spørsmålet.

JOURNALUTDRAG:
{context}

SPØRSMÅL: {question}

SVAR (oppgi alltid kilde-dokumenter med tittel og dato):"""
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 2000, "num_ctx": 8192},
                },
            )
            if response.status_code == 200:
                return response.json().get("response", "Ingen respons fra AI-modellen.")
            return f"Feil ved kontakt med AI-modell: {response.status_code}"
    except Exception as e:
        return f"Kunne ikke koble til AI-tjenesten: {str(e)}"


@router.post("/query", response_model=AIResponse)
async def ai_query(query: AIQuery, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if "ai_query" not in user_permissions(current_user.role):
        raise HTTPException(status_code=403, detail="Din rolle har ikke tilgang til AI-søk")

    rows = await retrieve_relevant_docs(db, query.question, limit=8)

    context_parts, source_docs = [], []
    for item in rows:
        doc = item[0]
        hn = item[1]
        snippet = (doc.ocr_text or "")[:1800]
        header = f"[Dokument: {doc.title} | Dato: {doc.document_date} | Sykehus: {hn or 'ukjent'}"
        if doc.sender:
            header += f" | Fra: {doc.sender}"
        if doc.recipient:
            header += f" | Til: {doc.recipient}"
        header += "]"
        context_parts.append(f"{header}\n{snippet}")
        source_docs.append({
            "id": str(doc.id), "title": doc.title,
            "date": str(doc.document_date) if doc.document_date else None,
            "document_type": doc.document_type, "hospital_name": hn,
        })

    context = "\n\n---\n\n".join(context_parts) if context_parts else "Ingen relevante dokumenter funnet."
    answer = await query_ollama(query.question, context)

    db.add(AuditLog(user_id=current_user.id, action="ai_query", resource_type="ai",
                    details={"question": query.question, "sources": len(source_docs)}))
    await db.commit()

    return AIResponse(answer=answer, source_documents=source_docs, model_used=settings.OLLAMA_MODEL)


@router.get("/status")
async def ai_status():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return {"status": "online", "models": [m["name"] for m in models],
                        "configured_model": settings.OLLAMA_MODEL}
    except Exception:
        pass
    return {"status": "offline", "models": [], "configured_model": settings.OLLAMA_MODEL}
