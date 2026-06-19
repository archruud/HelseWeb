"""
Bygg korrespondanse-tråder og trekk ut avsender/mottaker fra dokumenter.
Kjøres inne i backend-containeren:
    docker exec helsejournal-api python3 /app/build_threads.py

Dette skriptet:
- Trekker ut avsender (forfatter/avdeling) og mottaker fra OCR-tekst
- Identifiserer om et dokument er et svar (henvisning -> svar)
- Grupperer relaterte dokumenter med en felles correspondence_key
"""
import os
import re
import hashlib
import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://helsejournal:" + os.environ.get("DB_PASSWORD", "") + "@postgres:5432/helsejournal",
)
# Fallback: read from env DATABASE_URL (async form) and convert
if "asyncpg" in DB_URL:
    DB_URL = DB_URL.replace("+asyncpg", "")


def extract_sender_recipient(text: str):
    """Heuristic extraction of sender/recipient from Norwegian medical docs."""
    sender = None
    recipient = None
    is_reply = False

    # Recipient patterns
    m = re.search(r"Mottaker(?:\(e\))?[:\s]+([^\n]{3,80})", text, re.IGNORECASE)
    if m:
        recipient = m.group(1).strip()
    m = re.search(r"Henvisning til[:\s]+([^\n]{3,80})", text, re.IGNORECASE)
    if m and not recipient:
        recipient = m.group(1).strip()

    # Sender patterns (author / department)
    m = re.search(r"v/\s*(?:overlege|lege|lis-lege|psykolog|sykepleier)?\s*([A-ZÆØÅ][^\n/,]{3,50})", text)
    if m:
        sender = m.group(1).strip()
    m = re.search(r"Henvisende lege[:\s]+([^\n]{3,60})", text, re.IGNORECASE)
    if m and not sender:
        sender = m.group(1).strip()

    # Reply detection
    if re.search(r"svar(?:rapport|notat)?|vedr(?:\.|ørende) henvisning|viser til (?:henvisning|brev)", text, re.IGNORECASE):
        is_reply = True

    return sender, recipient, is_reply


def correspondence_key(doc_type: str, dept: str, year: int):
    """Group documents into a correspondence by department + topic + period."""
    base = f"{(dept or 'ukjent').lower().strip()}"
    return hashlib.md5(base.encode()).hexdigest()[:12]


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, title, document_type, department, ocr_text, document_date, hospital_id, file_path FROM documents")
    rows = cur.fetchall()
    print(f"Behandler {len(rows)} dokumenter...")

    updated = 0
    for (doc_id, title, dtype, dept, ocr, ddate, hid, fpath) in rows:
        text = (ocr or "")[:5000]
        sender, recipient, is_reply = extract_sender_recipient(text)

        # content hash for duplicate detection (Steg 8)
        chash = None
        if text.strip():
            chash = hashlib.sha256(text.strip().encode()).hexdigest()

        year = ddate.year if ddate else 0
        # Correspondence by department + hospital (groups a dialog within a unit)
        ckey = hashlib.md5(f"{hid}-{(dept or 'ukjent').lower()}".encode()).hexdigest()[:12]

        cur.execute(
            "UPDATE documents SET sender=%s, recipient=%s, is_reply=%s, correspondence_key=%s, content_hash=%s WHERE id=%s",
            (sender, recipient, is_reply, ckey, chash, doc_id),
        )
        updated += 1
        if updated % 100 == 0:
            conn.commit()
            print(f"  {updated} oppdatert...")

    conn.commit()
    cur.close()
    conn.close()
    print(f"FERDIG! {updated} dokumenter oppdatert med tråd-metadata.")


if __name__ == "__main__":
    main()
