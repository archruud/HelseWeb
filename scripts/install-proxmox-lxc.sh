#!/bin/bash
# ============================================================
# Helsejournal PHR - Installasjonsskript for Proxmox LXC
# ============================================================
# 
# Dette skriptet kjøres INNE I en privilegert LXC-container
# på Proxmox VE 9.x
#
# Forutsetninger:
#   - Privilegert LXC-container (Ubuntu 24.04)
#   - Minst 8GB RAM tildelt containeren
#   - NAS montert på /mnt/nas (for dokumentlagring)
#   - GPU passthrough konfigurert (for AI-container)
#   - Nettverkstilgang
#
# Bruk:
#   1. Opprett LXC-container i Proxmox (se README)
#   2. Kopier dette prosjektet inn i containeren
#   3. Kjør: sudo bash scripts/install-proxmox-lxc.sh
#
# ============================================================

set -e

echo "============================================================"
echo "  Helsejournal PHR - Installasjon starter"
echo "============================================================"

# Farger for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Sjekk at vi kjører som root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Feil: Kjør dette skriptet som root (sudo)${NC}"
    exit 1
fi

# ============================================================
# 1. System-oppdatering og grunnpakker
# ============================================================
echo -e "${GREEN}[1/8] Oppdaterer system og installerer grunnpakker...${NC}"
apt-get update && apt-get upgrade -y
apt-get install -y \
    curl wget git \
    ca-certificates gnupg lsb-release \
    build-essential \
    tesseract-ocr tesseract-ocr-nor tesseract-ocr-eng \
    poppler-utils \
    nfs-common cifs-utils \
    ufw

# ============================================================
# 2. Installer Docker
# ============================================================
echo -e "${GREEN}[2/8] Installerer Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Installer Docker Compose plugin
apt-get install -y docker-compose-plugin

# ============================================================
# 3. Installer NVIDIA Container Toolkit (for GPU)
# ============================================================
echo -e "${GREEN}[3/8] Installerer NVIDIA Container Toolkit...${NC}"
if command -v nvidia-smi &> /dev/null; then
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update
    apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    echo -e "${GREEN}  GPU funnet og konfigurert!${NC}"
else
    echo -e "${YELLOW}  Ingen NVIDIA GPU funnet. AI-funksjoner vil kjøre på CPU.${NC}"
fi

# ============================================================
# 4. Opprett mapper og monter NAS
# ============================================================
echo -e "${GREEN}[4/8] Oppretter mappestruktur...${NC}"
mkdir -p /opt/helsejournal
mkdir -p /mnt/nas/helsejournal/documents
mkdir -p /mnt/nas/helsejournal/private
mkdir -p /data/documents
mkdir -p /data/private

# Hvis NAS ikke er montert, bruk lokal lagring
if ! mountpoint -q /mnt/nas; then
    echo -e "${YELLOW}  NAS ikke montert. Bruker lokal lagring.${NC}"
    echo -e "${YELLOW}  For å montere NAS, legg til i /etc/fstab:${NC}"
    echo -e "${YELLOW}  //NAS_IP/share /mnt/nas cifs credentials=/root/.smbcredentials,uid=0,gid=0 0 0${NC}"
    # Bruk lokale mapper i stedet
    ln -sf /data/documents /mnt/nas/helsejournal/documents 2>/dev/null || true
    ln -sf /data/private /mnt/nas/helsejournal/private 2>/dev/null || true
fi

# ============================================================
# 5. Kopier prosjektfiler
# ============================================================
echo -e "${GREEN}[5/8] Kopierer prosjektfiler...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cp -r "$PROJECT_DIR" /opt/helsejournal/app
cd /opt/helsejournal/app

# ============================================================
# 6. Generer sikkerhetsnøkler
# ============================================================
echo -e "${GREEN}[6/8] Genererer sikkerhetsnøkler...${NC}"
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

cat > /opt/helsejournal/app/docker/.env << EOF
SECRET_KEY=${SECRET_KEY}
DB_PASSWORD=${DB_PASSWORD}
OLLAMA_MODEL=llama3:8b
FRONTEND_URL=http://localhost:3000
EOF

echo -e "${GREEN}  Hemmeligheter lagret i /opt/helsejournal/app/docker/.env${NC}"

# ============================================================
# 7. Bygg og start tjenestene
# ============================================================
echo -e "${GREEN}[7/8] Bygger og starter Docker-containere...${NC}"
cd /opt/helsejournal/app/docker
docker compose up -d --build

# Vent på at PostgreSQL er klar
echo "  Venter på database..."
sleep 10

# ============================================================
# 8. Initialiser database og opprett admin-bruker
# ============================================================
echo -e "${GREEN}[8/8] Initialiserer database...${NC}"

# Kjør schema
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal < /opt/helsejournal/app/backend/schema.sql 2>/dev/null || true

# Opprett admin-bruker
ADMIN_PASS=$(openssl rand -hex 8)
docker exec helsejournal-api python3 -c "
from passlib.context import CryptContext
pwd = CryptContext(schemes=['bcrypt'])
hash = pwd.hash('${ADMIN_PASS}')
print(hash)
" > /tmp/admin_hash.txt

ADMIN_HASH=$(cat /tmp/admin_hash.txt)
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal << EOSQL
INSERT INTO users (username, password_hash, full_name, role, email)
VALUES ('admin', '${ADMIN_HASH}', 'Administrator', 'admin', 'admin@helsejournal.local')
ON CONFLICT (username) DO NOTHING;
EOSQL

# Last ned AI-modell
echo -e "${GREEN}  Laster ned AI-modell (dette kan ta noen minutter)...${NC}"
docker exec helsejournal-ai ollama pull llama3:8b 2>/dev/null &

# ============================================================
# Ferdig!
# ============================================================
echo ""
echo "============================================================"
echo -e "${GREEN}  INSTALLASJON FULLFØRT!${NC}"
echo "============================================================"
echo ""
echo "  Webgrensesnitt:  http://$(hostname -I | awk '{print $1}'):80"
echo "  API:             http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
echo "  Admin-innlogging:"
echo "    Brukernavn: admin"
echo "    Passord:    ${ADMIN_PASS}"
echo ""
echo -e "${YELLOW}  VIKTIG: Skriv ned admin-passordet! Det vises ikke igjen.${NC}"
echo ""
echo "  Neste steg:"
echo "    1. Logg inn som admin"
echo "    2. Last opp journaldokumenter (PDF-filene)"
echo "    3. Opprett brukerkontoer for leger/advokater"
echo ""
echo "  AI-modellen lastes ned i bakgrunnen."
echo "  Sjekk status: docker logs helsejournal-ai"
echo "============================================================"
