# Helsejournal PHR - Komplett Installasjonsveiledning

**Sist oppdatert:** 11. juni 2026

Denne veiledningen tar deg fra en tom LXC-container til et fullt fungerende helsejournal-system med webgrensesnitt, database, AI og dokumenthåndtering.

---

## Forutsetninger

Du har allerede:
- En privilegert LXC-container (ID 300+) med Ubuntu 24.04 eller Debian 12/13
- Nettverkstilgang via vmbr1, VLAN 31, statisk IP i 192.168.31.0/24
- Nesting aktivert
- GPU passthrough konfigurert med Nvidia Data Center Driver 595.71.05
- `nvidia-smi` fungerer inne i containeren

---

## Steg 1: Oppdater systemet og installer grunnpakker

```bash
apt update && apt upgrade -y

apt install -y \
    curl wget git sudo \
    ca-certificates gnupg lsb-release \
    build-essential python3 python3-pip python3-venv \
    tesseract-ocr tesseract-ocr-nor tesseract-ocr-eng \
    poppler-utils \
    nfs-common cifs-utils \
    unzip htop tmux
```

---

## Steg 2: Installer Docker

```bash
# Installer Docker via offisielt skript
curl -fsSL https://get.docker.com | sh

# Aktiver Docker ved oppstart
systemctl enable docker
systemctl start docker

# Verifiser
docker --version
docker compose version
```

---

## Steg 3: Installer NVIDIA Container Toolkit

```bash
# Legg til Nvidia repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt update
apt install -y nvidia-container-toolkit

# Konfigurer Docker til å bruke Nvidia runtime
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Verifiser at Docker ser GPU-ene
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

Forventet output: Du skal se dine Nvidia A2-kort listet.

---

## Steg 4: Opprett mappestruktur

```bash
# Hovedmappe for applikasjonen
mkdir -p /opt/helsejournal

# Data-mapper (tilpass til din NAS-montering om ønskelig)
mkdir -p /data/documents
mkdir -p /data/private
mkdir -p /data/postgres
mkdir -p /data/redis
mkdir -p /data/chromadb
mkdir -p /data/ollama
```

**Valgfritt - Monter NAS:**

Hvis du vil lagre dokumenter på NAS i stedet for lokalt, legg til i `/etc/fstab`:

```bash
# For SMB/CIFS (tilpass IP og share-navn)
# //192.168.x.x/helsejournal /data/documents cifs credentials=/root/.smbcredentials,uid=0,gid=0,file_mode=0644,dir_mode=0755 0 0

# For NFS (tilpass IP og path)
# 192.168.x.x:/volume1/helsejournal /data/documents nfs defaults 0 0
```

For SMB, opprett credentials-fil:
```bash
cat > /root/.smbcredentials << 'EOF'
username=DITT_NAS_BRUKERNAVN
password=DITT_NAS_PASSORD
EOF
chmod 600 /root/.smbcredentials
```

Monter:
```bash
mount -a
```

---

## Steg 5: Last ned og pakk ut prosjektet

```bash
cd /opt/helsejournal

# Alternativ A: Kopier tar.gz-filen hit (fra din maskin)
# scp helsejournal-app.tar.gz root@192.168.31.X:/opt/helsejournal/

# Pakk ut
tar xzf helsejournal-app.tar.gz
cd helsejournal-app
```

---

## Steg 6: Generer sikkerhetsnøkler og opprett .env

```bash
cd /opt/helsejournal/helsejournal-app/docker

# Generer tilfeldige nøkler
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

# Opprett .env-fil
cat > .env << EOF
SECRET_KEY=${SECRET_KEY}
DB_PASSWORD=${DB_PASSWORD}
OLLAMA_MODEL=llama3:8b
FRONTEND_URL=http://192.168.31.X:3000
EOF

echo ""
echo "=== Genererte hemmeligheter ==="
echo "DB_PASSWORD: ${DB_PASSWORD}"
echo "SECRET_KEY: ${SECRET_KEY}"
echo "================================"
echo ""
echo "VIKTIG: Noter disse verdiene et trygt sted!"
```

Bytt ut `192.168.31.X` med din faktiske container-IP.

---

## Steg 7: Tilpass docker-compose.yml (valgfritt)

Hvis du bruker NAS-montering, rediger volume-bindingene i docker-compose.yml:

```bash
nano /opt/helsejournal/helsejournal-app/docker/docker-compose.yml
```

Endre `documents_data` og `private_data` volumes fra:
```yaml
  documents_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nas/helsejournal/documents
```

Til:
```yaml
  documents_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/documents
```

(Gjør tilsvarende for `private_data`.)

---

## Steg 8: Bygg og start alle tjenester

```bash
cd /opt/helsejournal/helsejournal-app/docker

# Bygg alle images og start i bakgrunnen
docker compose up -d --build

# Følg med på oppstarten
docker compose logs -f
```

Vent til du ser at alle containere er "healthy". Trykk `Ctrl+C` for å avslutte log-visningen.

**Sjekk status:**
```bash
docker compose ps
```

Forventet output - alle skal vise "Up":
```
helsejournal-db       Up (healthy)
helsejournal-redis    Up
helsejournal-api      Up
helsejournal-web      Up
helsejournal-ai       Up
helsejournal-proxy    Up
```

---

## Steg 9: Initialiser databasen

```bash
# Kjør SQL-skjemaet
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal < /opt/helsejournal/helsejournal-app/backend/schema.sql

# Verifiser at tabellene ble opprettet
docker exec helsejournal-db psql -U helsejournal -d helsejournal -c "\dt"
```

Du skal se tabeller som `users`, `documents`, `hospitals`, `annotations`, etc.

---

## Steg 10: Opprett admin-bruker

```bash
# Generer et admin-passord
ADMIN_PASS=$(openssl rand -hex 8)
echo "Admin-passord: ${ADMIN_PASS}"

# Opprett passordhash inne i backend-containeren
ADMIN_HASH=$(docker exec helsejournal-api python3 -c "
from passlib.context import CryptContext
pwd = CryptContext(schemes=['bcrypt'])
print(pwd.hash('${ADMIN_PASS}'))
")

# Sett inn admin-bruker i databasen
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal << EOSQL
INSERT INTO users (username, password_hash, full_name, role, email)
VALUES ('admin', '${ADMIN_HASH}', 'Terje Johan Ruud', 'admin', 'admin@helsejournal.local')
ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash;
EOSQL

echo ""
echo "========================================="
echo "  ADMIN-KONTO OPPRETTET"
echo "========================================="
echo "  Brukernavn: admin"
echo "  Passord:    ${ADMIN_PASS}"
echo "========================================="
echo ""
echo "  SKRIV NED PASSORDET! Det vises ikke igjen."
```

---

## Steg 11: Last ned AI-modell

```bash
# Last ned Llama 3 (8B) - tar ca. 4-5 minutter
docker exec helsejournal-ai ollama pull llama3:8b

# Verifiser at modellen er lastet
docker exec helsejournal-ai ollama list

# Valgfritt: Last ned embedding-modell for RAG-søk
docker exec helsejournal-ai ollama pull nomic-embed-text
```

For bedre kvalitet (krever mer VRAM, men du har nok):
```bash
# Llama 3 70B (kvantisert) - tar ca. 30 minutter å laste ned
docker exec helsejournal-ai ollama pull llama3:70b-instruct-q4_K_M
```

---

## Steg 12: Verifiser at alt fungerer

```bash
# Test backend API
curl http://localhost:8000/api/health
# Forventet: {"status":"ok","version":"1.0.0"}

# Test AI-tilkobling
curl http://localhost:11434/api/tags
# Forventet: Liste over installerte modeller

# Test frontend (fra din maskin)
# Åpne nettleser: http://192.168.31.X:80
```

---

## Steg 13: Importer journaldokumenter

Kopier de splittede PDF-filene inn i containeren:

```bash
# Fra din lokale maskin:
scp Helsejournal_splittet_per_sykehus.zip root@192.168.31.X:/data/documents/

# Inne i containeren:
cd /data/documents
unzip Helsejournal_splittet_per_sykehus.zip
```

Dokumentene vil nå ligge i mapper per sykehus under `/data/documents/`.

For å importere dem i databasen (kjør dette skriptet):

```bash
cat > /opt/helsejournal/import_documents.py << 'PYTHON'
#!/usr/bin/env python3
"""Import PDF documents into the helsejournal database."""
import os
import re
import subprocess
from datetime import datetime

import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://helsejournal:DITT_DB_PASSORD@localhost:5432/helsejournal")

# Hospital mapping
HOSPITAL_MAP = {
    "01_Sykehuset_Telemark_HF": 1,
    "02_Sykehuset_Østfold_Kalnes": 2,
    "03_Sykehuset_Østfold_Moss": 3,
    "04_Sykehuset_Østfold_Fredrikstad": 4,
    "05_Sykehuset_Østfold_Askim": 5,
    "06_Sykehuset_Østfold_Halden": 6,
    "08_Sykehuset_Østfold_Ukjent_lokasjon": 2,  # Default to Kalnes
}

def extract_text_from_pdf(pdf_path):
    """Extract text using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception:
        return ""

def parse_filename(filename):
    """Parse document info from filename like 001_31. mai 2018 09_Epikrise somatikk.pdf"""
    match = re.match(r'\d+_(.+?)_(.+)\.pdf', filename)
    if match:
        date_str = match.group(1).strip()
        title = match.group(2).strip()
        return date_str, title
    return None, filename

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    base_dir = "/data/documents"
    imported = 0
    
    for hospital_dir in sorted(os.listdir(base_dir)):
        hospital_path = os.path.join(base_dir, hospital_dir)
        if not os.path.isdir(hospital_path):
            continue
        
        hospital_id = HOSPITAL_MAP.get(hospital_dir)
        if not hospital_id:
            continue
        
        print(f"\nImporterer fra: {hospital_dir}")
        
        for filename in sorted(os.listdir(hospital_path)):
            if not filename.endswith('.pdf'):
                continue
            
            filepath = os.path.join(hospital_path, filename)
            date_str, title = parse_filename(filename)
            
            # Extract text
            ocr_text = extract_text_from_pdf(filepath)
            
            # Determine category
            category = "somatic"
            if "psykiatri" in title.lower() or "PS " in title:
                category = "psychiatric"
            elif "TSB" in title or "RUS" in title.upper():
                category = "tsb"
            
            # Determine document type
            doc_type = "Ukjent"
            if "pikrise" in title.lower():
                doc_type = "Epikrise"
            elif "innkomst" in title.lower():
                doc_type = "Innkomstjournal"
            elif "operasjon" in title.lower():
                doc_type = "Operasjonsbeskrivelse"
            elif "notat" in title.lower():
                doc_type = "Notat"
            elif "utskrivning" in title.lower():
                doc_type = "Utskrivningsnotat"
            elif "biopsi" in title.lower() or "histolog" in title.lower():
                doc_type = "Prøvesvar"
            elif "henvisning" in title.lower():
                doc_type = "Henvisning"
            elif "kurve" in title.lower() or "medikasjon" in title.lower():
                doc_type = "Kurve/Medikasjon"
            
            # Get file size
            file_size = os.path.getsize(filepath)
            
            # Insert into database
            cur.execute("""
                INSERT INTO documents (title, document_type, category, hospital_id, 
                                      file_path, file_size_bytes, ocr_text, uploaded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (title, doc_type, category, hospital_id, filepath, file_size, ocr_text[:100000]))
            
            imported += 1
            if imported % 50 == 0:
                print(f"  ... {imported} dokumenter importert")
                conn.commit()
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"\nFerdig! Totalt {imported} dokumenter importert.")

if __name__ == "__main__":
    main()
PYTHON

# Installer psycopg2 og kjør import
pip3 install psycopg2-binary

# Kjør importen (bytt ut DITT_DB_PASSORD med passordet fra steg 6)
DATABASE_URL="postgresql://helsejournal:DITT_DB_PASSORD@localhost:5432/helsejournal" python3 /opt/helsejournal/import_documents.py
```

---

## Steg 14: Sett opp automatisk oppstart

```bash
# Opprett systemd-service for Docker Compose
cat > /etc/systemd/system/helsejournal.service << 'EOF'
[Unit]
Description=Helsejournal PHR
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/helsejournal/helsejournal-app/docker
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable helsejournal.service
```

---

## Steg 15: Test innlogging

1. Åpne nettleser på din maskin
2. Gå til: `http://192.168.31.X` (din container-IP)
3. Logg inn med:
   - Brukernavn: `admin`
   - Passord: (det du noterte i steg 10)

---

## Nyttige kommandoer

```bash
# Se logger
docker compose -f /opt/helsejournal/helsejournal-app/docker/docker-compose.yml logs -f

# Restart alle tjenester
docker compose -f /opt/helsejournal/helsejournal-app/docker/docker-compose.yml restart

# Restart kun backend
docker compose -f /opt/helsejournal/helsejournal-app/docker/docker-compose.yml restart backend

# Stopp alt
docker compose -f /opt/helsejournal/helsejournal-app/docker/docker-compose.yml down

# Start alt
docker compose -f /opt/helsejournal/helsejournal-app/docker/docker-compose.yml up -d

# Sjekk GPU-bruk
docker exec helsejournal-ai nvidia-smi

# Gå inn i database
docker exec -it helsejournal-db psql -U helsejournal -d helsejournal

# Sjekk diskbruk
docker system df

# Oppdater AI-modell
docker exec helsejournal-ai ollama pull llama3:8b
```

---

## Feilsøking

**Problem: Docker ser ikke GPU**
```bash
# Sjekk at nvidia-smi fungerer på hosten (inne i LXC)
nvidia-smi

# Sjekk at nvidia-container-toolkit er installert
dpkg -l | grep nvidia-container

# Restart Docker
systemctl restart docker
```

**Problem: Backend starter ikke**
```bash
# Sjekk logger
docker compose logs backend

# Vanlig årsak: Database ikke klar ennå
docker compose restart backend
```

**Problem: Kan ikke nå websiden**
```bash
# Sjekk at nginx kjører
docker compose ps nginx

# Sjekk at port 80 er åpen
ss -tlnp | grep :80

# Test lokalt
curl http://localhost:80
```

**Problem: AI svarer ikke**
```bash
# Sjekk at Ollama kjører
docker compose logs ollama

# Sjekk at modell er lastet
docker exec helsejournal-ai ollama list

# Test manuelt
docker exec helsejournal-ai ollama run llama3:8b "Hei, fungerer du?"
```

---

## Oppsummering av porter

| Tjeneste | Port | Beskrivelse |
|----------|------|-------------|
| Nginx (hovedinngang) | 80 | Webgrensesnitt |
| Backend API | 8000 | REST API + Swagger docs (/docs) |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Ollama | 11434 | AI/LLM API |
| Frontend (dev) | 3000 | Vite dev server (kun utvikling) |

---

## Sikkerhet

Siden serveren står i ditt hus på et dedikert VLAN (31), er sikkerheten allerede god. Men her er noen ekstra tiltak:

```bash
# Begrens tilgang til kun ditt VLAN
# (kun nødvendig hvis du har routing mellom VLAN-er)
iptables -A INPUT -s 192.168.31.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j DROP
iptables -A INPUT -p tcp --dport 8000 -j DROP
```

---

**Ferdig!** Systemet skal nå være oppe og kjøre. Logg inn via nettleseren og begynn å bruke det.
