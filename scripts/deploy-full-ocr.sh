#!/bin/bash
# ============================================================
# FULL bilde-OCR på alle dokumenter + reindeksering (HelseWeb)
# Kjøres i containeren etter 'git pull'.
# ============================================================
# Dette:
# 1. Tar backup
# 2. Bygger backend
# 3. Nullstiller OCR-flagg (kjør på nytt fra start)
# 4. Kjører ekte bilde-OCR på ALLE dokumenter (tungt - bruker mange kjerner)
# 5. Kjører dato-oppdeling + embeddings på nytt
# ============================================================
set -e

APP=/opt/helsejournal/helsejournal-app
cd "$APP/docker"
DBPW=$(grep DB_PASSWORD .env | cut -d= -f2)

echo "[1/5] Backup av database..."
mkdir -p /data/backups
docker exec helsejournal-db pg_dump -U helsejournal helsejournal | gzip > /data/backups/pre-fullocr-$(date +%Y%m%d_%H%M).sql.gz || true

echo "[2/5] Bygger backend..."
docker compose up -d --build backend
sleep 8

echo "[3/5] Nullstiller OCR-flagg (full ny kjøring)..."
docker exec helsejournal-db psql -U helsejournal -d helsejournal -c "UPDATE documents SET ai_indexed = FALSE;"

echo "[4/5] Kjører EKTE bilde-OCR på alle dokumenter (dette tar lang tid - kan kjøres i bakgrunnen)..."
echo "      Du kan følge fremdrift. Avbryt med Ctrl+C - den gjenopptar der den slapp ved ny kjøring."
docker exec -e DATABASE_URL_SYNC="postgresql://helsejournal:${DBPW}@postgres:5432/helsejournal" \
    -e OCR_WORKERS="12" \
    helsejournal-api python3 /app/run_ocr_full.py

echo "[5/5] Oppdaterer daterte oppføringer + semantiske embeddings..."
docker exec -e DATABASE_URL_SYNC="postgresql://helsejournal:${DBPW}@postgres:5432/helsejournal" \
    -e OLLAMA_URL="http://ollama:11434" \
    helsejournal-api python3 /app/build_entries.py

echo ""
echo "============================================================"
echo "  Full OCR + reindeksering fullført!"
echo "  - Alt skjult/skannet innhold er nå hentet ut (inkl. 1980/90-tallet)"
echo "  - Søk på innhold og tidsrom fungerer på tvers av alle år"
echo "============================================================"
