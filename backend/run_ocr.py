"""
OCR-prosessering av skannede/uleselige dokumenter (HelseWeb).
Kjøres inne i backend-containeren:
    docker exec helsejournal-api python3 /app/run_ocr.py

Hva skriptet gjør:
- Finner dokumenter med lite/ingen lesbar tekst (gamle skannede papirjournaler)
- Kjører OCR med norsk Tesseract (via ocrmypdf om tilgjengelig, ellers pdf2image+pytesseract)
- Oppdaterer ocr_text i databasen (gjør dem søkbare + lesbare for AI)
- Forsøker å trekke ut dokumentdato fra teksten der den mangler
- search_vector oppdateres automatisk av database-triggeren

Trygt å kjøre flere ganger - hopper over dokumenter som allerede har god tekst.
"""
import os
import re
import subprocess
import tempfile
import psycopg2

DB_URL = os.environ.get("DATABASE_URL_SYNC")
if not DB_URL:
    pw = os.environ.get("DB_PASSWORD", "")
    DB_URL = f"postgresql://helsejournal:{pw}@postgres:5432/helsejournal"
if "asyncpg" in DB_URL:
    DB_URL = DB_URL.replace("+asyncpg", "")

# Threshold: documents with less than this many chars of text are considered "needs OCR"
MIN_TEXT_LEN = 80

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mai': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12,
          'januar': 1, 'februar': 2, 'mars': 3, 'april': 4, 'juni': 6, 'juli': 7,
          'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12}


def extract_date(text: str):
    """Try to find a date in Norwegian formats: dd.mm.yyyy, dd.mm.yy, dd. month yyyy."""
    # dd.mm.yyyy or dd.mm.yy
    m = re.search(r'\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b', text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 1900 if y > 30 else 2000
        if 1 <= mo <= 12 and 1 <= d <= 31 and 1960 <= y <= 2026:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    # dd. month yyyy
    m = re.search(r'\b(\d{1,2})\.?\s*([a-zæøå]+)\.?\s*(\d{4})\b', text.lower())
    if m and m.group(2)[:3] in MONTHS:
        d, mo, y = int(m.group(1)), MONTHS[m.group(2)[:3]], int(m.group(3))
        if 1960 <= y <= 2026:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def ocr_pdf(pdf_path: str) -> str:
    """Run OCR on a PDF and return extracted text. Tries ocrmypdf, falls back to pdf2image+pytesseract."""
    # Method 1: ocrmypdf (best - adds text layer)
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out_pdf = tmp.name
        r = subprocess.run(
            ["ocrmypdf", "-l", "nor+eng", "--force-ocr", "--optimize", "0",
             "--sidecar", out_pdf + ".txt", pdf_path, out_pdf],
            capture_output=True, text=True, timeout=300,
        )
        if os.path.exists(out_pdf + ".txt"):
            txt = open(out_pdf + ".txt", encoding="utf-8", errors="ignore").read()
            os.unlink(out_pdf + ".txt")
            if os.path.exists(out_pdf):
                os.unlink(out_pdf)
            if txt.strip():
                return txt
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Method 2: pdf2image + pytesseract
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(pdf_path, dpi=300)
        parts = []
        for img in images:
            parts.append(pytesseract.image_to_string(img, lang="nor+eng"))
        return "\n".join(parts)
    except Exception as e:
        return ""


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, file_path, ocr_text, document_date FROM documents "
        "ORDER BY document_date NULLS FIRST"
    )
    rows = cur.fetchall()

    need_ocr = [r for r in rows if not r[3] or len(r[3].strip()) < MIN_TEXT_LEN]
    print(f"Totalt {len(rows)} dokumenter. {len(need_ocr)} trenger OCR.")

    done = 0
    for (doc_id, title, fpath, old_text, ddate) in need_ocr:
        if not fpath or not os.path.exists(fpath):
            continue
        text = ocr_pdf(fpath)
        if not text.strip():
            continue

        new_date = None
        if not ddate:
            new_date = extract_date(text[:1500])

        if new_date:
            cur.execute("UPDATE documents SET ocr_text=%s, document_date=%s WHERE id=%s",
                        (text[:100000], new_date, doc_id))
        else:
            cur.execute("UPDATE documents SET ocr_text=%s WHERE id=%s",
                        (text[:100000], doc_id))
        done += 1
        if done % 10 == 0:
            conn.commit()
            print(f"  OCR fullført for {done}/{len(need_ocr)} dokumenter...")

    conn.commit()
    cur.close()
    conn.close()
    print(f"FERDIG! OCR kjørt på {done} dokumenter. De er nå søkbare og lesbare for AI.")


if __name__ == "__main__":
    main()
