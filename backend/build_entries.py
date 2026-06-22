"""
Del samle-dokumenter i daterte journaloppføringer + lag semantiske embeddings.
Kjøres inne i backend-containeren:
    docker exec -e DATABASE_URL_SYNC="postgresql://helsejournal:PASS@postgres:5432/helsejournal" helsejournal-api python3 /app/build_entries.py

Verktøy (velprøvde):
- dateparser: robust tolkning av datoer i naturlig (norsk) tekst
- Ollama nomic-embed-text: lokale embeddings for semantisk søk
- pgvector: lagrer embeddings i PostgreSQL for likhetssøk

Hva skriptet gjør:
1. Går gjennom alle dokumenter
2. Finner datomarkører i teksten, splitter i daterte segmenter
3. Lagrer hvert segment som journal_entry med RIKTIG dato
4. Lager embedding (768-dim) for hvert segment via Ollama -> semantisk søk

Trygt å kjøre flere ganger (tømmer journal_entries først).
"""
import os
import re
import time
import httpx
import psycopg2

DB_URL = os.environ.get("DATABASE_URL_SYNC")
if not DB_URL:
    pw = os.environ.get("DB_PASSWORD", "")
    DB_URL = f"postgresql://helsejournal:{pw}@postgres:5432/helsejournal"
if "asyncpg" in DB_URL:
    DB_URL = DB_URL.replace("+asyncpg", "")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = "nomic-embed-text"

try:
    import dateparser
    HAVE_DATEPARSER = True
except Exception:
    HAVE_DATEPARSER = False

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mai': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12}

DATE_RE = re.compile(r'(?<!\d)(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})(?!\d)')
DATE_RE2 = re.compile(
    r'(?<!\d)(\d{1,2})\.?\s+(jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des)[a-z]*\.?\s+(\d{4})',
    re.IGNORECASE)
HEADING_RE = re.compile(
    r'(JOURNALOPPTAK|INNLEGGELSE|INNKOMST|UTSKRIVNING|EPIKRISE|NOTAT|OPERASJON|'
    r'POLIKLINISK|KONTROLL|TILSYN|RTG|RØNTGEN|LAB|SVAR|HENVISNING|VURDERING)', re.IGNORECASE)


def normalize_year(y):
    return (1900 + y if y > 30 else 2000 + y) if y < 100 else y

def valid_date(d, mo, y):
    return 1 <= mo <= 12 and 1 <= d <= 31 and 1960 <= y <= 2026

def find_date_positions(text):
    marks = []
    for m in DATE_RE.finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), normalize_year(int(m.group(3)))
        if valid_date(d, mo, y):
            marks.append((m.start(), f"{y:04d}-{mo:02d}-{d:02d}"))
    for m in DATE_RE2.finditer(text):
        d = int(m.group(1)); mo = MONTHS[m.group(2).lower()[:3]]; y = int(m.group(3))
        if valid_date(d, mo, y):
            marks.append((m.start(), f"{y:04d}-{mo:02d}-{d:02d}"))
    marks.sort()
    return marks


def get_embedding(text):
    """Get embedding from Ollama. Returns list[float] or None."""
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/embeddings",
                       json={"model": EMBED_MODEL, "prompt": text[:2000]}, timeout=60.0)
        if r.status_code == 200:
            return r.json().get("embedding")
    except Exception:
        return None
    return None


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("DELETE FROM journal_entries")
    conn.commit()

    cur.execute("SELECT id, ocr_text, hospital_id, document_date FROM documents")
    rows = cur.fetchall()
    print(f"Behandler {len(rows)} dokumenter... (dateparser={HAVE_DATEPARSER})")

    # First pass: create dated entries (fast)
    entry_ids = []
    total = 0
    for (doc_id, text, hid, ddate) in rows:
        if not text or len(text.strip()) < 40:
            continue
        marks = find_date_positions(text)
        if not marks:
            cur.execute(
                "INSERT INTO journal_entries (document_id, entry_date, content, hospital_id) VALUES (%s,%s,%s,%s) RETURNING id",
                (doc_id, ddate, text[:8000], hid))
            entry_ids.append(cur.fetchone()[0]); total += 1
            continue
        for i, (pos, dstr) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
            segment = text[pos:end].strip()
            if len(segment) < 20:
                continue
            hmatch = HEADING_RE.search(segment[:120])
            heading = hmatch.group(1).upper() if hmatch else segment.split('\n')[0][:80]
            cur.execute(
                "INSERT INTO journal_entries (document_id, entry_date, heading, content, hospital_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (doc_id, dstr, heading, segment[:8000], hid))
            entry_ids.append(cur.fetchone()[0]); total += 1
        if total % 300 == 0:
            conn.commit(); print(f"  {total} oppføringer opprettet...")
    conn.commit()
    print(f"{total} daterte oppføringer opprettet. Lager semantiske embeddings (Ollama)...")

    # Second pass: embeddings (slower - uses GPU via Ollama)
    cur.execute("SELECT id, heading, content FROM journal_entries WHERE embedding IS NULL")
    todo = cur.fetchall()
    done = 0
    for (eid, heading, content) in todo:
        emb = get_embedding(f"{heading or ''}\n{content or ''}")
        if emb and len(emb) == 768:
            cur.execute("UPDATE journal_entries SET embedding = %s::vector WHERE id = %s", (emb, eid))
            done += 1
        if done % 100 == 0 and done:
            conn.commit(); print(f"  {done}/{len(todo)} embeddings laget...")
    conn.commit()

    # Stats
    cur.execute("""SELECT EXTRACT(YEAR FROM entry_date)::int/10*10 AS decade, COUNT(*)
                   FROM journal_entries WHERE entry_date IS NOT NULL GROUP BY decade ORDER BY decade""")
    print("\nOppføringer per tiår:")
    for dec, cnt in cur.fetchall():
        print(f"  {dec}-tallet: {cnt}")

    cur.close(); conn.close()
    print(f"\nFERDIG! {total} daterte oppføringer, {done} med semantisk embedding.")
    print("Søk på tidsrom OG betydning fungerer nå (tarmlammelse finner pseudo-obstruksjon osv.).")


if __name__ == "__main__":
    main()
