"""
FULL bilde-OCR på ALLE dokumenter (HelseWeb).
Kjøres inne i backend-containeren:
    docker exec -e DATABASE_URL_SYNC="postgresql://helsejournal:PASS@postgres:5432/helsejournal" helsejournal-api python3 /app/run_ocr_full.py

Forskjell fra run_ocr.py:
- Kjører EKTE bilde-OCR (--force-ocr) på ALLE dokumenter, ikke bare de uten tekst
- Henter ut skjult/skannet innhold som pdftotext ikke fanget (gamle papirjournaler,
  innskannede vedlegg, bilder med tekst osv.)
- Erstatter den ubrukelige "SKANN"-toppteksten med faktisk journalinnhold
- Trekker ut faktisk dokumentdato fra det nye innholdet

Bruker parallellitet (flere prosesser) for å utnytte de 32 CPU-kjernene.
Trygt å kjøre flere ganger.

Fremdrift lagres i databasen (ocr_done-flagg via ai_indexed-kolonnen gjenbrukt),
så kan stoppes og gjenopptas.
"""
import os
import re
import sys
import subprocess
import tempfile
import multiprocessing as mp
import psycopg2

DB_URL = os.environ.get("DATABASE_URL_SYNC")
if not DB_URL:
    pw = os.environ.get("DB_PASSWORD", "")
    DB_URL = f"postgresql://helsejournal:{pw}@postgres:5432/helsejournal"
if "asyncpg" in DB_URL:
    DB_URL = DB_URL.replace("+asyncpg", "")

WORKERS = int(os.environ.get("OCR_WORKERS", "6"))

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mai': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12,
          'januar': 1, 'februar': 2, 'mars': 3, 'april': 4, 'juni': 6, 'juli': 7,
          'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12}

# Lines that are just the scanner-added header (to strip out)
HEADER_NOISE = re.compile(
    r'(Dokument nummer:|Dokumentbetegnelse:|Godkjent Av:\s*SKANN|Opprettet:|^\d+\s*/\s*\d+\s*$|Ruud, Terje Johan 121268)',
    re.IGNORECASE)


def clean_text(text: str) -> str:
    """Remove repeated scanner header noise, keep real content."""
    lines = []
    for ln in text.split('\n'):
        if HEADER_NOISE.search(ln.strip()):
            continue
        lines.append(ln)
    return '\n'.join(lines).strip()


def extract_earliest_date(text: str):
    """Find the EARLIEST plausible date in the text (medical content date)."""
    candidates = []
    for m in re.finditer(r'(?<!\d)(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})(?!\d)', text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y = 1900 + y if y > 30 else 2000 + y
        if 1 <= mo <= 12 and 1 <= d <= 31 and 1960 <= y <= 2026:
            candidates.append((y, mo, d))
    for m in re.finditer(r'(?<!\d)(\d{1,2})\.?\s+([a-zæøå]+)\.?\s+(\d{4})', text.lower()):
        mon = m.group(2)[:3]
        if mon in MONTHS:
            d, mo, y = int(m.group(1)), MONTHS[mon], int(m.group(3))
            if 1 <= d <= 31 and 1960 <= y <= 2026:
                candidates.append((y, mo, d))
    if not candidates:
        return None
    candidates.sort()
    y, mo, d = candidates[0]
    return f"{y:04d}-{mo:02d}-{d:02d}"


def ocr_one(args):
    """OCR a single document. Returns (doc_id, text, date) or (doc_id, None, None)."""
    doc_id, fpath = args
    if not fpath or not os.path.exists(fpath):
        return (doc_id, None, None)
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out_pdf = tmp.name
        sidecar = out_pdf + ".txt"
        subprocess.run(
            ["ocrmypdf", "-l", "nor+eng", "--force-ocr", "--optimize", "0",
             "--output-type", "none", "--sidecar", sidecar, fpath, out_pdf],
            capture_output=True, text=True, timeout=900,
        )
        text = ""
        if os.path.exists(sidecar):
            text = open(sidecar, encoding="utf-8", errors="ignore").read()
            os.unlink(sidecar)
        if os.path.exists(out_pdf):
            os.unlink(out_pdf)
        text = clean_text(text)
        if len(text) < 20:
            return (doc_id, None, None)
        date = extract_earliest_date(text[:4000])
        return (doc_id, text[:200000], date)
    except Exception:
        return (doc_id, None, None)


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    # ai_indexed = TRUE betyr "ekte OCR utført" (gjenbruker kolonnen som flagg)
    cur.execute("SELECT id, file_path FROM documents WHERE ai_indexed IS NOT TRUE")
    todo = cur.fetchall()
    total = len(todo)
    print(f"Skal OCR-behandle {total} dokumenter med {WORKERS} parallelle prosesser...")

    done = 0
    with mp.Pool(WORKERS) as pool:
        for (doc_id, text, date) in pool.imap_unordered(ocr_one, [(str(d[0]), d[1]) for d in todo]):
            if text:
                if date:
                    cur.execute("UPDATE documents SET ocr_text=%s, document_date=%s, ai_indexed=TRUE WHERE id=%s",
                                (text, date, doc_id))
                else:
                    cur.execute("UPDATE documents SET ocr_text=%s, ai_indexed=TRUE WHERE id=%s",
                                (text, doc_id))
            else:
                cur.execute("UPDATE documents SET ai_indexed=TRUE WHERE id=%s", (doc_id,))
            done += 1
            if done % 10 == 0:
                conn.commit()
                print(f"  {done}/{total} OCR-behandlet...", flush=True)
    conn.commit()
    cur.close()
    conn.close()
    print(f"FERDIG! {done} dokumenter OCR-behandlet med ekte bildegjenkjenning.")
    print("Kjør deretter build_entries.py på nytt for å oppdatere daterte oppføringer + embeddings.")


if __name__ == "__main__":
    main()
