"""Semantic retrieval using pgvector + Ollama embeddings, with keyword fallback."""
import httpx
from sqlalchemy import text as sql_text
from app.config import settings

EMBED_MODEL = "nomic-embed-text"


async def get_query_embedding(query: str):
    """Get embedding vector for a search query from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{settings.OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": query[:2000]},
            )
            if r.status_code == 200:
                emb = r.json().get("embedding")
                if emb and len(emb) == 768:
                    return emb
    except Exception:
        pass
    return None


async def semantic_search_entries(db, query: str, limit: int = 8):
    """Return journal entries ranked by semantic similarity (pgvector cosine).
    Falls back to keyword search if embeddings/Ollama unavailable.
    Returns list of dicts with date, hospital, heading, content, document_id.
    """
    emb = await get_query_embedding(query)
    if emb:
        vec_literal = "[" + ",".join(str(x) for x in emb) + "]"
        sql = sql_text("""
            SELECT je.id, je.document_id, je.entry_date, je.heading, je.content,
                   h.name AS hospital_name, d.title AS doc_title,
                   1 - (je.embedding <=> CAST(:vec AS vector)) AS similarity
            FROM journal_entries je
            LEFT JOIN hospitals h ON je.hospital_id = h.id
            LEFT JOIN documents d ON je.document_id = d.id
            WHERE je.embedding IS NOT NULL
            ORDER BY je.embedding <=> CAST(:vec AS vector)
            LIMIT :lim
        """)
        rows = (await db.execute(sql, {"vec": vec_literal, "lim": limit})).fetchall()
        if rows:
            return [{
                "document_id": str(r[1]), "entry_date": str(r[2]) if r[2] else None,
                "heading": r[3], "content": r[4], "hospital_name": r[5],
                "doc_title": r[6], "similarity": float(r[7]) if r[7] is not None else 0.0,
            } for r in rows]

    # Fallback: keyword full-text search
    sql = sql_text("""
        SELECT je.id, je.document_id, je.entry_date, je.heading, je.content,
               h.name AS hospital_name, d.title AS doc_title,
               ts_rank(je.search_vector, plainto_tsquery('norwegian', :q)) AS rank
        FROM journal_entries je
        LEFT JOIN hospitals h ON je.hospital_id = h.id
        LEFT JOIN documents d ON je.document_id = d.id
        WHERE je.search_vector @@ plainto_tsquery('norwegian', :q)
        ORDER BY rank DESC
        LIMIT :lim
    """)
    rows = (await db.execute(sql, {"q": query, "lim": limit})).fetchall()
    return [{
        "document_id": str(r[1]), "entry_date": str(r[2]) if r[2] else None,
        "heading": r[3], "content": r[4], "hospital_name": r[5],
        "doc_title": r[6], "similarity": 0.0,
    } for r in rows]
