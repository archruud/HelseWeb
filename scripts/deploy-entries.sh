#!/bin/bash
# ============================================================
# Deploy kronologisk oppdeling + semantisk søk (HelseWeb)
# - Deler samle-dokumenter i daterte journaloppføringer
# - Aktiverer pgvector og lager semantiske embeddings (Ollama)
# Kjøres i containeren etter 'git pull'.
# ============================================================
set -e

APP=/opt/helsejournal/helsejournal-app
cd "$APP/docker"

DBPW=$(grep DB_PASSWORD .env | cut -d= -f2)

echo "[1/5] Backup av database..."
mkdir -p /data/backups
docker exec helsejournal-db pg_dump -U helsejournal helsejournal | gzip > /data/backups/pre-entries-$(date +%Y%m%d_%H%M).sql.gz || true

echo "[2/5] Oppgraderer database-image til pgvector (data beholdes)..."
docker compose up -d postgres
sleep 8
docker exec helsejournal-db psql -U helsejournal -d helsejournal -c 'CREATE EXTENSION IF NOT EXISTS vector;'

echo "[3/5] Bygger backend..."
docker compose up -d --build backend
sleep 8

echo "[4/5] Oppretter tabell for journaloppføringer (+ pgvector)..."
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal < "$APP/backend/migrations_entries.sql"

echo "[5/5] Deler dokumenter i daterte oppføringer + lager embeddings (kan ta flere minutter)..."
docker exec -e DATABASE_URL_SYNC="postgresql://helsejournal:${DBPW}@postgres:5432/helsejournal" \
    -e OLLAMA_URL="http://ollama:11434" \
    helsejournal-api python3 /app/build_entries.py

echo ""
echo "============================================================"
echo "  Kronologisk oppdeling + semantisk søk fullført!"
echo "  - Søk i innhold etter EKTE dato (1990-1995 osv.)"
echo "  - Semantisk AI-søk (forstår betydning, ikke bare ord)"
echo "  - Tidslinje: kjør 'Generer fra dokumenter' på nytt i web"
echo "============================================================"
