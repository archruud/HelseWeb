# Helsejournal PHR - Personlig Helsejournal Webapplikasjon

Et komplett, selv-hostet system for å administrere, søke i, og analysere personlige helsejournaler med AI-støtte. Designet for å kjøre på Proxmox VE med privilegerte LXC-containere og Nvidia GPU-akselerasjon.

---

## Funksjoner

- **Trevisning:** Navigasjon via År → Måned → Sykehus → Dokument
- **Fulltekstsøk:** Søk i alle dokumenter med filtrering på sykehus, dato, type
- **Dokumenttråder:** Relaterte dokumenter (henvisning → svar → epikrise) lenkes automatisk
- **Pasientnotater:** Legg til "gule lapper" på dokumenter (korrigeringer, merknader)
- **Tidslinje:** Visuell oversikt over viktige hendelser i sykdomsforløpet
- **AI Assistent:** Spør AI-en om innholdet i journalene (lokal LLM via Ollama)
- **Private filer:** Last opp egne lydopptak, transkripsjoner etc. adskilt fra offisiell journal
- **Rollestyring (RBAC):** Admin, Lege, Spesialist, Psykolog, Advokat, Gjest
- **Revisjonsspor:** All tilgang logges

---

## Systemkrav

| Komponent | Minimum | Anbefalt |
|-----------|---------|----------|
| CPU | 4 kjerner | 8+ kjerner |
| RAM | 8 GB | 16+ GB |
| Disk | 50 GB + NAS | 50 GB + NAS |
| GPU | Ingen (CPU-modus) | Nvidia A2 / A4000+ |
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 i Proxmox LXC |

---

## Installasjon på Proxmox

### Steg 1: Opprett LXC-container

Kjør på **Proxmox-hosten** (ikke inne i en container):

```bash
# Last ned og kjør opprettelse-skriptet
sudo bash scripts/create-lxc-proxmox.sh
```

Dette oppretter en privilegert LXC-container med:
- 16 GB RAM, 8 CPU-kjerner, 50 GB disk
- GPU passthrough for Nvidia A2
- Nesting aktivert (for Docker inne i LXC)

### Steg 2: Kopier prosjektet inn i containeren

```bash
# Pakk prosjektet
tar czf helsejournal-app.tar.gz helsejournal-app/

# Kopier inn i container (CTID=200)
pct push 200 helsejournal-app.tar.gz /root/helsejournal-app.tar.gz
```

### Steg 3: Installer inne i containeren

```bash
# Gå inn i containeren
pct enter 200

# Pakk ut og installer
cd /root
tar xzf helsejournal-app.tar.gz
cd helsejournal-app
sudo bash scripts/install-proxmox-lxc.sh
```

Skriptet vil:
1. Installere Docker og NVIDIA Container Toolkit
2. Bygge og starte alle tjenester (PostgreSQL, Redis, Backend, Frontend, Ollama, Nginx)
3. Opprette admin-bruker med tilfeldig passord
4. Laste ned AI-modellen i bakgrunnen

### Steg 4: Logg inn

Åpne nettleseren og gå til containerens IP-adresse. Logg inn med admin-brukernavnet og passordet som ble vist i terminalen.

---

## NAS-konfigurasjon

For å lagre dokumenter på din NAS (50 TB), rediger `/etc/pve/lxc/200.conf` på Proxmox-hosten:

```
# SMB/CIFS mount
lxc.mount.entry: //NAS_IP/helsejournal mnt/nas cifs credentials=/root/.smbcredentials,uid=0,gid=0 0 0
```

Eller for NFS:
```
lxc.mount.entry: NAS_IP:/volume1/helsejournal mnt/nas nfs defaults 0 0
```

Opprett credentials-fil:
```bash
echo "username=ditt_nas_brukernavn" > /root/.smbcredentials
echo "password=ditt_nas_passord" >> /root/.smbcredentials
chmod 600 /root/.smbcredentials
```

---

## Mappestruktur

```
helsejournal-app/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── main.py         # Hovedapplikasjon
│   │   ├── config.py       # Konfigurasjon
│   │   ├── database.py     # Database-tilkobling
│   │   ├── models.py       # SQLAlchemy-modeller
│   │   └── routers/        # API-endepunkter
│   │       ├── auth.py     # Autentisering (JWT)
│   │       ├── documents.py # Dokumenthåndtering
│   │       ├── annotations.py # Pasientnotater
│   │       ├── ai_assistant.py # AI/RAG
│   │       └── ...
│   ├── schema.sql           # Database-skjema
│   └── requirements.txt
├── frontend/                # React/TypeScript frontend
│   ├── src/
│   │   ├── components/     # UI-komponenter (Sidebar, TreeView)
│   │   ├── pages/          # Sider (Dashboard, Search, Timeline, AI)
│   │   ├── stores/         # State management (Zustand)
│   │   └── api/            # API-klient (Axios)
│   └── package.json
├── docker/                  # Docker-konfigurasjon
│   ├── docker-compose.yml   # Alle tjenester
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx.conf
├── scripts/                 # Installasjonsskript
│   ├── create-lxc-proxmox.sh  # Kjøres på Proxmox-host
│   └── install-proxmox-lxc.sh # Kjøres inne i LXC
└── docs/                    # Dokumentasjon
```

---

## Teknologistakk

| Lag | Teknologi |
|-----|-----------|
| Frontend | React 18, TypeScript, TailwindCSS, Vite |
| Backend | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| AI/LLM | Ollama + Llama 3 (lokal, GPU-akselerert) |
| OCR | Tesseract (norsk + engelsk) |
| Vektor-DB | ChromaDB (for RAG-søk) |
| Proxy | Nginx |
| Container | Docker Compose (inne i Proxmox LXC) |

---

## Roller og tilganger

| Rolle | Se somatikk | Se psykiatri | Se private | Laste opp | Notere | AI-søk | Eksport | Admin |
|-------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Lege | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | - |
| Spesialist | ✓ | - | - | - | - | ✓ | ✓ | - |
| Psykolog | - | ✓ | - | - | ✓ | - | - | - |
| Advokat | ✓ | - | - | - | - | - | ✓ | - |
| Gjest | ✓ | - | - | - | - | - | - | - |

---

## Importere eksisterende journaler

Etter installasjon kan du importere de allerede splittede PDF-filene:

```bash
# Kopier de splittede journalfilene inn i containeren
pct push 200 Helsejournal_splittet_per_sykehus.zip /data/import/

# Gå inn og kjør import
pct enter 200
cd /data/import && unzip Helsejournal_splittet_per_sykehus.zip
# Bruk admin-grensesnittet for å laste opp, eller kjør import-skript (kommer)
```

---

## Lisens

Privat bruk. Ikke for distribusjon.
