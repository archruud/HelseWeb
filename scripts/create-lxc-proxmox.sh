#!/bin/bash
# ============================================================
# Helsejournal PHR - Opprett LXC Container på Proxmox
# ============================================================
#
# Kjør dette skriptet på PROXMOX-HOSTEN (ikke inne i en container)
#
# Bruk: sudo bash create-lxc-proxmox.sh
#
# ============================================================

set -e

# Konfigurasjon - tilpass disse verdiene
CTID=200                          # Container ID
HOSTNAME="helsejournal"
STORAGE="local-lvm"              # Proxmox storage for rootfs
TEMPLATE="local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
MEMORY=16384                      # 16 GB RAM
SWAP=4096                         # 4 GB swap
CORES=8                           # 8 CPU cores
DISK_SIZE=50                      # 50 GB root disk
BRIDGE="vmbr0"                    # Network bridge
IP="dhcp"                         # Bruk "dhcp" eller sett fast IP: "192.168.1.100/24"
GATEWAY=""                        # Sett gateway hvis fast IP: "192.168.1.1"

echo "============================================================"
echo "  Oppretter LXC Container for Helsejournal PHR"
echo "  Container ID: ${CTID}"
echo "============================================================"

# Sjekk at template eksisterer, last ned om nødvendig
if ! pveam list local | grep -q "ubuntu-24.04"; then
    echo "Laster ned Ubuntu 24.04 template..."
    pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst
fi

# Opprett containeren (PRIVILEGERT for GPU-passthrough og NFS)
echo "Oppretter container..."
pct create ${CTID} ${TEMPLATE} \
    --hostname ${HOSTNAME} \
    --memory ${MEMORY} \
    --swap ${SWAP} \
    --cores ${CORES} \
    --rootfs ${STORAGE}:${DISK_SIZE} \
    --net0 name=eth0,bridge=${BRIDGE},ip=${IP}${GATEWAY:+,gw=$GATEWAY} \
    --features nesting=1 \
    --unprivileged 0 \
    --ostype ubuntu \
    --start 0

# Konfigurer GPU passthrough (Nvidia A2)
echo "Konfigurerer GPU passthrough..."
cat >> /etc/pve/lxc/${CTID}.conf << 'EOF'

# GPU Passthrough for Nvidia A2
lxc.cgroup2.devices.allow: c 195:* rwm
lxc.cgroup2.devices.allow: c 234:* rwm
lxc.cgroup2.devices.allow: c 237:* rwm
lxc.mount.entry: /dev/nvidia0 dev/nvidia0 none bind,optional,create=file
lxc.mount.entry: /dev/nvidia1 dev/nvidia1 none bind,optional,create=file
lxc.mount.entry: /dev/nvidiactl dev/nvidiactl none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm dev/nvidia-uvm none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm-tools dev/nvidia-uvm-tools none bind,optional,create=file

# NAS mount (tilpass path til din NAS)
# lxc.mount.entry: /mnt/nas mnt/nas none bind,create=dir 0 0
EOF

# Start containeren
echo "Starter container..."
pct start ${CTID}

# Vent litt
sleep 5

# Installer grunnleggende pakker inne i containeren
echo "Installerer grunnpakker i container..."
pct exec ${CTID} -- bash -c "apt-get update && apt-get install -y curl wget git sudo"

echo ""
echo "============================================================"
echo "  LXC Container opprettet og startet!"
echo "============================================================"
echo ""
echo "  Container ID: ${CTID}"
echo "  Hostname:     ${HOSTNAME}"
echo "  RAM:          ${MEMORY} MB"
echo "  CPU Cores:    ${CORES}"
echo "  Disk:         ${DISK_SIZE} GB"
echo ""
echo "  Neste steg:"
echo "    1. Kopier helsejournal-app mappen inn i containeren:"
echo "       pct push ${CTID} helsejournal-app.tar.gz /root/helsejournal-app.tar.gz"
echo ""
echo "    2. Gå inn i containeren:"
echo "       pct enter ${CTID}"
echo ""
echo "    3. Pakk ut og installer:"
echo "       cd /root && tar xzf helsejournal-app.tar.gz"
echo "       cd helsejournal-app && sudo bash scripts/install-proxmox-lxc.sh"
echo ""
echo "  For NAS-montering, rediger /etc/pve/lxc/${CTID}.conf"
echo "  og legg til riktig mount-path til din NAS."
echo "============================================================"
