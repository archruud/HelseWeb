#!/bin/bash
# ============================================================
# Kjør OCR på gamle skannede dokumenter (HelseWeb)
# ============================================================
# Bygger backend på nytt med OCR-verktøy, kjører OCR-prosessering.
# Kjøres i containeren etter 'git pull'.
# ============================================================
set -e

APP=/opt/helsejournal/helsejournal-app
cd "$APP/docker"

echo "[1/3] Tar backup av database..."
mkdir -p /data/backups
docker exec helsejournal-db pg_dump -U helsejournal helsejournal | gzip > /data/backups/pre-ocr-$(date +%Y%m%d_%H%M).sql.gz || true

echo "[2/3] Bygger backend med OCR-verktøy (ocrmypdf, tesseract-nor)..."
docker compose up -d --build backend
sleep 8

echo "[3/3] Kjører OCR på skannede dokumenter (dette kan ta en stund)..."
docker exec -e DATABASE_URL_SYNC="postgresql://helsejournal:${DB_PASSWORD}@postgres:5432/helsejournal" helsejournal-api python3 /app/run_ocr.py

echo ""
echo "============================================================"
echo "  OCR fullført!"
echo "  Gamle dokumenter er nå søkbare og lesbare for AI."
echo "  Oppdater nettleseren - flere år skal nå vises i treet."
echo "============================================================"
