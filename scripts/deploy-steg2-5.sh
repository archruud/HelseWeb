#!/bin/bash
# ============================================================
# Deploy Steg 2-5 (HelseWeb)
# Kjøres i containeren etter 'git pull'
# ============================================================
set -e

APP=/opt/helsejournal/helsejournal-app
cd "$APP/docker"

echo "[1/4] Tar backup av database før migrasjon..."
mkdir -p /data/backups
docker exec helsejournal-db pg_dump -U helsejournal helsejournal | gzip > /data/backups/pre-steg2-5-$(date +%Y%m%d_%H%M).sql.gz || true

echo "[2/4] Bygger backend og frontend..."
docker compose up -d --build backend frontend

echo "[3/4] Venter på backend..."
sleep 8

echo "[4/4] Kjører database-migrasjon (roller, søk, tråder, tidslinje)..."
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal < "$APP/backend/migrations_steg2-5.sql"

echo "Bygger søkeindeks og tråd-metadata (kan ta et par minutter)..."
docker exec helsejournal-api python3 /app/build_threads.py

echo ""
echo "============================================================"
echo "  Steg 2-5 deployet!"
echo "  - Roller: admin / super_editor / editor / viewer"
echo "  - Forbedret søk (gruppert per avdeling)"
echo "  - RAG-AI med kilder og tråder"
echo "  - Tidslinje (bruk 'Generer fra dokumenter' i web)"
echo ""
echo "  Endre admin-passord: bash $APP/scripts/endre-admin-passord.sh"
echo "============================================================"
