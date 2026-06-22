"""AI Assistant router - semantic RAG over dated journal entries with citations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
import httpx

from app.config import settings
from app.database import get_db
from app.models import AuditLog, User
from app.routers.auth import get_current_user, user_permissions
from app.semantic import semantic_search_entries

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
- Du skal ALLTID oppgi hvilke dokumenter/datoer du baserer svaret på.
- Du skal ALDRI stille diagnoser eller gi behandlingsråd - kun gjengi og oppsummere journalinnhold.
- Du skal svare på norsk, presist og strukturert, og være kildekritisk.
- Hvis informasjon mangler i utdragene, si det tydelig.
- Beskriv kronologi når det er relevant (når skjedde hva).
- Vær spesielt oppmerksom på forhold relevant for CIPO (kronisk intestinal pseudo-obstruksjon):
  tarmmotilitet, pseudo-obstruksjon, intravenøs/parenteral ernæring, langvarige magesmerter, pankreas."""


async def query_ollama(question: str, context: str) -> str:
    full_prompt = f"""Basert på følgende daterte journalutdrag, svar på spørsmålet.

JOURNALUTDRAG (med dato og sykehus):
{context}

SPØRSMÅL: {question}

SVAR (oppgi alltid dato og kilde for det du nevner):"""
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

    # Semantic retrieval over dated journal entries
    hits = await semantic_search_entries(db, query.question, limit=8)

    context_parts, source_docs, seen_docs = [], [], set()
    for h in hits:
        header = f"[Dato: {h['entry_date']} | Sykehus: {h['hospital_name'] or 'ukjent'}"
        if h.get("heading"):
            header += f" | {h['heading']}"
        header += "]"
        context_parts.append(f"{header}\n{(h['content'] or '')[:1600]}")
        if h["document_id"] not in seen_docs:
            seen_docs.add(h["document_id"])
            source_docs.append({
                "id": h["document_id"],
                "title": f"{h.get('heading') or h.get('doc_title') or 'Journal'} ({h['entry_date']})",
                "date": h["entry_date"],
                "hospital_name": h["hospital_name"],
            })

    context = "\n\n---\n\n".join(context_parts) if context_parts else "Ingen relevante journaloppføringer funnet."
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
