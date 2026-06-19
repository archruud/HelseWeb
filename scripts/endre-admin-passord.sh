#!/bin/bash
# ============================================================
# Endre system-admin passord (HelseWeb)
# ============================================================
# System-admin passord kan KUN endres via dette skriptet (ikke via web),
# av sikkerhetshensyn.
#
# Bruk: bash scripts/endre-admin-passord.sh
# ============================================================

set -e

echo "============================================================"
echo "  Endre passord for system-admin (HelseWeb)"
echo "============================================================"
echo ""

# Be om nytt passord
read -s -p "Skriv nytt admin-passord: " PASS1
echo ""
read -s -p "Bekreft nytt passord: " PASS2
echo ""

if [ "$PASS1" != "$PASS2" ]; then
    echo "FEIL: Passordene er ikke like. Avbryter."
    exit 1
fi

if [ ${#PASS1} -lt 6 ]; then
    echo "FEIL: Passordet må være minst 6 tegn. Avbryter."
    exit 1
fi

# Generer bcrypt-hash inne i backend-containeren
HASH=$(docker exec helsejournal-api python3 -c "import bcrypt; print(bcrypt.hashpw('${PASS1}'.encode()[:72], bcrypt.gensalt()).decode())")

# Oppdater i databasen (kun system-admin)
docker exec -i helsejournal-db psql -U helsejournal -d helsejournal -c \
    "UPDATE users SET password_hash='${HASH}' WHERE is_system_admin = TRUE;"

echo ""
echo "============================================================"
echo "  Admin-passord er endret!"
echo "============================================================"
