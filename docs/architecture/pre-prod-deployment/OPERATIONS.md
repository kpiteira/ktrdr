# Pre-Production Deployment Operations

## Manual Procedures & Runbooks

**Version**: 1.0
**Status**: Operational Guide
**Date**: 2025-11-16

---

## Purpose

This document contains **manual operational procedures** for pre-production infrastructure:

- LXC provisioning
- Network configuration
- NFS setup
- Backup automation
- Disaster recovery

**For technical specs**: See [ARCHITECTURE.md](ARCHITECTURE.md)
**For design decisions**: See [DESIGN.md](DESIGN.md)

---

## Infrastructure Verification Record

**Last Verified**: 2025-11-25
**Verified By**: Task 5.1 (Pre-prod Deployment Plan)

### LXC Summary

| Node | Hostname | IP Address | Role | RAM | CPUs | System Disk | Data Disk | Docker |
|------|----------|------------|------|-----|------|-------------|-----------|--------|
| A | backend | 10.42.1.10 | Core (DB, Backend, Observability) | 29GB | 4 | 50GB | 500GB (/srv/ktrdr-shared) | 29.0.4 |
| B | workers-b | 10.42.1.11 | Workers | 14GB | 3 | 30GB | - | 29.0.4 |
| C | workers-c | 10.42.1.12 | Workers | 6GB | 3 | 30GB | - | 29.0.4 |

### Verification Status

| Check | Status | Notes |
|-------|--------|-------|
| SSH Access (all nodes) | ✅ PASS | All 3 LXCs accessible via Tailscale DNS |
| Docker Installed | ✅ PASS | Docker 29.0.4 on all nodes |
| Disk Space (core >20GB) | ✅ PASS | 50GB available |
| Network Connectivity | ✅ PASS | 0% packet loss between all pairs |

### DNS Configuration

All hostnames resolve via `ktrdr.home.mynerd.place` zone:

```text
backend.ktrdr.home.mynerd.place    -> 10.42.1.10
workers-b.ktrdr.home.mynerd.place  -> 10.42.1.11
workers-c.ktrdr.home.mynerd.place  -> 10.42.1.12
```

---

## LXC Provisioning

### Prerequisites

**Proxmox Cluster**:

- 3 Proxmox nodes on shared VLAN
- Access to Proxmox web UI or CLI
- Ubuntu LTS template available (22.04 or 24.04)

**Resources Available**:

- Node A: 4 cores, 16GB RAM, 500GB data disk (for NFS, database, models, backups)
- Node B: 4 cores, 16GB RAM, 30GB disk
- Node C: 4 cores, 8GB RAM, 30GB disk

---

### Define Your Variables First

**IMPORTANT**: Before running any commands, set these variables in your SSH session on the Proxmox host:

```bash
# Ubuntu template (adjust to your actual template name)
UBUNTU_TEMPLATE="local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"

# Storage pool (adjust to your Proxmox storage: local-lvm, local-zfs, etc.)
STORAGE="local-zfs"

# Network configuration (adjust to match your VLAN setup)
BRIDGE="vmbr0"          # Your Proxmox bridge (e.g., vmbr0, vmbr42)
CORE_IP="192.168.1.10"
WORKER_B_IP="192.168.1.20"
WORKER_C_IP="192.168.1.30"
GATEWAY="192.168.1.1"
DNS_SERVER="192.168.1.1"
NETMASK="24"
```

Verify your template name:

```bash
pveam list local
```

---

### Step 1: Create Base Template (One-Time Setup)

Create a template LXC with all common software installed:

```bash
# 1. Create template LXC (ID 900) as PRIVILEGED (required for Tailscale)
pct create 900 $UBUNTU_TEMPLATE \
  --hostname ktrdr-template \
  --cores 2 \
  --memory 2048 \
  --swap 0 \
  --rootfs $STORAGE:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 0

# 2. Start template
pct start 900

# 3. Install all common software
pct exec 900 -- bash -c '
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release openssh-server nfs-common

  # Docker
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

  # Tailscale
  curl -fsSL https://tailscale.com/install.sh | sh

  # SSH setup
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh

  # Clean up
  apt-get clean
  rm -rf /var/lib/apt/lists/*
'

# 4. Stop and convert to template
pct stop 900
pct template 900
```

---

### Step 2: Clone and Configure Each LXC

#### Core LXC (Node A)

```bash
# Clone from template (inherits privileged mode from template)
pct clone 900 100 --hostname ktrdr-core --full

# Configure resources and network (50GB system disk)
pct set 100 \
  --cores 4 \
  --memory 30336 \
  --net0 name=eth0,bridge=$BRIDGE,ip=$CORE_IP/$NETMASK,gw=$GATEWAY \
  --nameserver $DNS_SERVER

# Resize rootfs to 50GB
pct resize 100 rootfs 50G

# Add 500GB data volume for NFS, database, models, backups
pct set 100 --mp0 $STORAGE:500,mp=/srv/ktrdr-shared

# Stop container to add TUN device support (required for Tailscale)
pct stop 100

# Add TUN device support for Tailscale
echo "lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net dev/net none bind,create=dir" >> /etc/pve/lxc/100.conf

# Create TUN device on Proxmox host (if not already present)
mkdir -p /dev/net
mknod /dev/net/tun c 10 200 2>/dev/null || true
chmod 666 /dev/net/tun

# Start the container
pct start 100

# Manually configure network (Proxmox's pct set doesn't auto-configure inside container)
pct exec 100 -- ip link set eth0 up
pct exec 100 -- ip addr add $CORE_IP/$NETMASK dev eth0
pct exec 100 -- ip route add default via $GATEWAY dev eth0

# Test network connectivity
pct exec 100 -- ping -c 3 $GATEWAY

# Start Tailscale daemon and authenticate
pct exec 100 -- systemctl start tailscaled
pct exec 100 -- systemctl enable tailscaled
pct exec 100 -- tailscale up
# Follow the URL printed to authorize in your browser

# Create Core-specific directories
pct exec 100 -- bash -c "
  mkdir -p /opt/ktrdr-core
  mkdir -p /srv/ktrdr-shared/{data,results,models,db-backups}
"
```

**Note**: SSH access from your workstation will be configured via Tailscale hostnames after all containers are provisioned.

#### Worker B LXC (Node B)

```bash
# Clone from template (inherits privileged mode from template)
pct clone 900 201 --hostname ktrdr-workers-b --full

# Configure resources and network
pct set 201 \
  --cores 3 \
  --memory 14336 \
  --net0 name=eth0,bridge=$BRIDGE,ip=$WORKER_B_IP/$NETMASK,gw=$GATEWAY \
  --nameserver $DNS_SERVER

# Resize rootfs to 30GB
pct resize 201 rootfs 30G

# Stop container to add TUN device support (required for Tailscale)
pct stop 201

# Add TUN device support for Tailscale
echo "lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net dev/net none bind,create=dir" >> /etc/pve/lxc/201.conf

# Start the container
pct start 201

# Manually configure network
pct exec 201 -- ip link set eth0 up
pct exec 201 -- ip addr add $WORKER_B_IP/$NETMASK dev eth0
pct exec 201 -- ip route add default via $GATEWAY dev eth0

# Test network connectivity
pct exec 201 -- ping -c 3 $GATEWAY

# Start Tailscale daemon and authenticate
pct exec 201 -- systemctl start tailscaled
pct exec 201 -- systemctl enable tailscaled
pct exec 201 -- tailscale up
# Follow the URL printed to authorize in your browser

# Create Worker-specific directories
pct exec 201 -- bash -c "
  mkdir -p /mnt/ktrdr-shared
  mkdir -p /opt/ktrdr-workers-b
"
```

#### Worker C LXC (Node C)

```bash
# Clone from template (inherits privileged mode from template)
pct clone 900 202 --hostname ktrdr-workers-c --full

# Configure resources and network (6GB RAM for smaller node)
pct set 202 \
  --cores 3 \
  --memory 6144 \
  --net0 name=eth0,bridge=$BRIDGE,ip=$WORKER_C_IP/$NETMASK,gw=$GATEWAY \
  --nameserver $DNS_SERVER

# Resize rootfs to 30GB
pct resize 202 rootfs 30G

# Stop container to add TUN device support (required for Tailscale)
pct stop 202

# Add TUN device support for Tailscale
echo "lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net dev/net none bind,create=dir" >> /etc/pve/lxc/202.conf

# Start the container
pct start 202

# Manually configure network
pct exec 202 -- ip link set eth0 up
pct exec 202 -- ip addr add $WORKER_C_IP/$NETMASK dev eth0
pct exec 202 -- ip route add default via $GATEWAY dev eth0

# Test network connectivity
pct exec 202 -- ping -c 3 $GATEWAY

# Start Tailscale daemon and authenticate
pct exec 202 -- systemctl start tailscaled
pct exec 202 -- systemctl enable tailscaled
pct exec 202 -- tailscale up
# Follow the URL printed to authorize in your browser

# Create Worker-specific directories
pct exec 202 -- bash -c "
  mkdir -p /mnt/ktrdr-shared
  mkdir -p /opt/ktrdr-workers-c
"
```

---

## Network Configuration

### DNS Configuration

**DNS Naming Strategy**: See [ktrdr-dns-naming.md](ktrdr-dns-naming.md) for complete DNS strategy

Add entries to your DNS server (BIND, Unbound, Pi-hole, etc.) for zone `ktrdr.home.mynerd.place`:

```bind
; KTRDR homelab infrastructure (ktrdr.home.mynerd.place zone)
; Core services
backend.ktrdr.home.mynerd.place.     IN A    <Node A IP>
postgres.ktrdr.home.mynerd.place.    IN A    <Node A IP>
grafana.ktrdr.home.mynerd.place.     IN A    <Node A IP>
prometheus.ktrdr.home.mynerd.place.  IN A    <Node A IP>

; Worker nodes
workers-b.ktrdr.home.mynerd.place.   IN A    <Node B IP>
workers-c.ktrdr.home.mynerd.place.   IN A    <Node C IP>
```

Reload DNS server:

```bash
rndc reload  # BIND
# OR
systemctl restart unbound  # Unbound
# OR
pihole restartdns  # Pi-hole
```

Test DNS resolution:

```bash
dig backend.ktrdr.home.mynerd.place
dig workers-b.ktrdr.home.mynerd.place
dig workers-c.ktrdr.home.mynerd.place
```

---

### Firewall Configuration

**Proxmox host level** (adjust to your firewall tool):

```bash
# Allow external access to Grafana, Jaeger, Backend API
iptables -A FORWARD -p tcp --dport 3000 -d <Node A IP> -j ACCEPT
iptables -A FORWARD -p tcp --dport 16686 -d <Node A IP> -j ACCEPT
iptables -A FORWARD -p tcp --dport 8000 -d <Node A IP> -j ACCEPT

# Allow worker → core communication
iptables -A FORWARD -p tcp -s <Node B IP> -d <Node A IP> --dport 8000 -j ACCEPT
iptables -A FORWARD -p tcp -s <Node C IP> -d <Node A IP> --dport 8000 -j ACCEPT

# Allow worker → core NFS
iptables -A FORWARD -p tcp -s <Node B IP> -d <Node A IP> --dport 2049 -j ACCEPT
iptables -A FORWARD -p tcp -s <Node C IP> -d <Node A IP> --dport 2049 -j ACCEPT

# Block external → workers (workers not externally accessible)
iptables -A FORWARD -d <Node B IP> -j DROP
iptables -A FORWARD -d <Node C IP> -j DROP
```

---

### Port Forwarding (Optional)

If accessing from outside Proxmox network:

```bash
# Forward external ports to core LXC
iptables -t nat -A PREROUTING -p tcp --dport 8000 -j DNAT --to-destination <Node A IP>:8000
iptables -t nat -A PREROUTING -p tcp --dport 3000 -j DNAT --to-destination <Node A IP>:3000
iptables -t nat -A PREROUTING -p tcp --dport 16686 -j DNAT --to-destination <Node A IP>:16686
```

---

## NFS Configuration

### Core LXC - NFS Server

**Already configured via docker-compose.core.yml**, but verify:

```bash
# Verify NFS container is running
ssh backend.ktrdr.home.mynerd.place
docker ps | grep nfs

# Test NFS export
showmount -e localhost
# Should show: /exports *
```

---

### Worker LXCs - NFS Client

Configure `/etc/fstab` on worker LXCs:

```bash
# On worker LXCs
ssh workers-b.ktrdr.home.mynerd.place

# Add to /etc/fstab
echo "backend.ktrdr.home.mynerd.place:/srv/ktrdr-shared  /mnt/ktrdr-shared  nfs  defaults,_netdev  0 0" | tee -a /etc/fstab

# Mount NFS share
mount -a

# Verify mount
df -h | grep ktrdr-shared
ls -la /mnt/ktrdr-shared
```

Repeat for `workers-c.ktrdr.home.mynerd.place`.

---

## Initial Deployment

### 1. Copy Configuration Files

```bash
# From Mac to core LXC
scp -r monitoring/ backend.ktrdr.home.mynerd.place:/opt/ktrdr-core/
scp docker-compose.core.yml backend.ktrdr.home.mynerd.place:/opt/ktrdr-core/docker-compose.core.yml

# To worker LXCs
scp docker-compose.workers.yml workers-b.ktrdr.home.mynerd.place:/opt/ktrdr-workers-b/docker-compose.workers.yml
scp docker-compose.workers.yml workers-c.ktrdr.home.mynerd.place:/opt/ktrdr-workers-c/docker-compose.workers.yml
```

---

### 2. Initial Secrets Setup

Create 1Password vault and items for KTRDR secrets management.

#### 1Password Structure

**Vault**: `KTRDR Homelab Secrets`

**Item**: `ktrdr-homelab-core`

| Field Label | Type | Description | Example/Requirements |
|-------------|------|-------------|---------------------|
| `db_username` | CONCEALED | Database username | `ktrdr` |
| `db_password` | CONCEALED | Database password | Strong, 20+ chars |
| `jwt_secret` | CONCEALED | JWT signing secret | Minimum 32 chars, random |
| `grafana_password` | CONCEALED | Grafana admin password | Strong, 16+ chars |
| `ghcr_token` | CONCEALED | GitHub PAT for GHCR | `read:packages` scope |

#### Field Naming Conventions

- **Lowercase with underscores**: Use `db_password` not `DB_PASSWORD` or `dbPassword`
- **Type = CONCEALED**: All secret fields must be marked as "Password" type in 1Password (shows as CONCEALED in JSON)
- **Label matches env var suffix**: Field label should match the suffix of the corresponding environment variable (e.g., `db_password` → `DB_PASSWORD`)
- **No special characters in labels**: Avoid spaces, hyphens, or special characters in field labels

#### Create Item via 1Password CLI

```bash
# Create item with all required fields
op item create \
  --category "Login" \
  --title "ktrdr-homelab-core" \
  --vault "KTRDR Homelab Secrets" \
  'db_username[password]=ktrdr' \
  'db_password[password]=YOUR_GENERATED_PASSWORD' \
  'jwt_secret[password]=YOUR_32_CHAR_SECRET' \
  'grafana_password[password]=YOUR_GRAFANA_PASSWORD' \
  'ghcr_token[password]=YOUR_GITHUB_PAT'
```

**Generate secure values**:

```bash
# Generate 32-char JWT secret
openssl rand -base64 32 | tr -d '/+=' | head -c 32

# Generate strong password
openssl rand -base64 24
```

#### Create Item via 1Password UI

1. Open 1Password → Create new vault "KTRDR Homelab Secrets" (if not exists)
2. Create new Login item named "ktrdr-homelab-core"
3. Add password fields (use the "Add More" → "Password" option for each):
   - `db_username`: `ktrdr`
   - `db_password`: Generate strong password
   - `jwt_secret`: Generate 32+ char random string
   - `grafana_password`: Generate strong password
   - `ghcr_token`: Your GitHub PAT with `read:packages` scope

#### Verify 1Password Access

```bash
# Check op CLI installed
op --version

# Sign in (if needed)
op signin

# Test item access
op item get ktrdr-homelab-core --format json | jq '.fields[] | {label: .label, type: .type}'

# Expected output (all should be CONCEALED):
# { "label": "db_username", "type": "CONCEALED" }
# { "label": "db_password", "type": "CONCEALED" }
# { "label": "jwt_secret", "type": "CONCEALED" }
# { "label": "grafana_password", "type": "CONCEALED" }
# { "label": "ghcr_token", "type": "CONCEALED" }

# Test fetching a specific value (should show value)
op item get ktrdr-homelab-core --fields db_username
```

#### Creating GitHub PAT for GHCR

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Generate new token with:
   - Name: `ktrdr-ghcr-read`
   - Expiration: Set appropriate expiration
   - Repository access: "Only select repositories" → select `ktrdr`
   - Permissions: `read:packages`
3. Copy token to 1Password `ghcr_token` field

#### Troubleshooting 1Password Access

**"not signed in" error**:

```bash
op signin
```

**"item not found" error**:

```bash
# List vaults to find correct name
op vault list

# List items in vault
op item list --vault "KTRDR Homelab Secrets"
```

**Fields showing as STRING instead of CONCEALED**:

- Edit item in 1Password UI
- Change field type from "Text" to "Password"

---

### 3. Deploy Core Services

```bash
# From Mac
ktrdr deploy core all
```

**Verify**:

```bash
ssh backend.ktrdr.home.mynerd.place
docker ps
# Should show: ktrdr-db, ktrdr-backend, ktrdr-prometheus, ktrdr-grafana, ktrdr-jaeger, ktrdr-nfs

# Check logs
docker logs ktrdr-backend
docker logs ktrdr-db
```

**Access UIs**:

- Backend: `http://backend.ktrdr.home.mynerd.place:8000/api/v1/docs`
- Grafana: `http://grafana.ktrdr.home.mynerd.place:3000`
- Jaeger: `http://backend.ktrdr.home.mynerd.place:16686`

---

### 4. Deploy Workers

```bash
# From Mac
ktrdr deploy workers B
ktrdr deploy workers C
```

**Verify**:

```bash
# Check workers registered with backend
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq

# Should show workers from both nodes
```

---

## Backup Procedures

### Database Backups

**Automated via cron on core LXC**:

**Note**: Backup automation is planned for v2. This section documents manual backup procedures.

```bash
ssh backend.ktrdr.home.mynerd.place

# Create backup script
cat > /opt/ktrdr-core/backup-db.sh <<'EOF'
#!/bin/bash
BACKUP_DIR=/srv/ktrdr-shared/db-backups
DATE=$(date +%Y%m%d)

# Dump database
docker exec ktrdr-db pg_dump -U ktrdr ktrdr | gzip > $BACKUP_DIR/ktrdr-$DATE.sql.gz

# Retention: keep last 30 days
find $BACKUP_DIR -name "ktrdr-*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/ktrdr-core/backup-db.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /opt/ktrdr-core/backup-db.sh
```

---

### NFS Snapshots (ZFS/btrfs)

If Node A uses ZFS for `/srv/ktrdr-shared`:

```bash
# On Node A Proxmox host
# Create hourly snapshots
zfs snapshot tank/ktrdr-shared@$(date +%Y%m%d-%H%M)

# Automated via cron
crontab -e
# Hourly (retain 24): 0 * * * * zfs snapshot tank/ktrdr-shared@$(date +\%Y\%m\%d-\%H\%M)
# Daily (retain 30): 0 3 * * * zfs snapshot tank/ktrdr-shared@daily-$(date +\%Y\%m\%d)

# Cleanup old snapshots
zfs list -t snapshot -o name,creation -s creation | grep ktrdr-shared | tail -n +25 | awk '{print $1}' | xargs -n 1 zfs destroy
```

---

### LXC Snapshots

**Proxmox UI**: Datacenter → LXC → Snapshots → Take Snapshot

**CLI**:

```bash
# Weekly snapshots
pct snapshot 100 weekly-$(date +%Y%m%d)
pct snapshot 201 weekly-$(date +%Y%m%d)
pct snapshot 202 weekly-$(date +%Y%m%d)

# Retention: keep last 4 weeks
pct listsnapshot 100 | tail -n +5 | awk '{print $1}' | xargs -n 1 pct delsnapshot 100
```

---

## Disaster Recovery

### Scenario A: Worker LXC Loss

**Recovery Time**: ~15 minutes

```bash
# 1. Recreate LXC from template (see LXC Provisioning section above)

# 2. Mount NFS share (see NFS Configuration section)
ssh workers-b.ktrdr.home.mynerd.place
mount -a

# 3. Deploy workers
ktrdr deploy workers B

# 4. Verify
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

---

### Scenario B: Core LXC Loss

**Recovery Time**: ~1 hour

```bash
# 1. Restore from Proxmox LXC snapshot
pct rollback 100 weekly-20251110

# OR recreate LXC from template
# (see LXC Provisioning section)

# 2. Restore database from backup
ssh backend.ktrdr.home.mynerd.place
gunzip < /srv/ktrdr-shared/db-backups/ktrdr-20251110.sql.gz | \
  docker exec -i ktrdr-db psql -U ktrdr ktrdr

# 3. Deploy core services
ktrdr deploy core all

# 4. Verify
docker ps
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health
```

---

### Scenario C: Complete Infrastructure Loss

**Recovery Time**: ~3 hours

```bash
# 1. Provision all LXCs (see LXC Provisioning section)

# 2. Configure network (see Network Configuration section)

# 3. Configure NFS (see NFS Configuration section)

# 4. Deploy core
ktrdr deploy core all

# 5. Restore database
# (see Scenario B step 2)

# 6. Deploy workers
ktrdr deploy workers B
ktrdr deploy workers C

# 7. Verify full system
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

---

## Operational Procedures

### Adding Worker Capacity

**Example**: Add 4th worker node (uses template created in LXC Provisioning)

```bash
# Set variables for new worker
WORKER_D_IP="192.168.1.103"

# 1. Clone from template (inherits privileged mode from template)
pct clone 900 203 --hostname ktrdr-workers-d --full

# 2. Configure resources and network
pct set 203 \
  --cores 3 \
  --memory 14336 \
  --net0 name=eth0,bridge=vmbr0,ip=$WORKER_D_IP/$NETMASK,gw=$GATEWAY \
  --nameserver $DNS_SERVER

# Resize rootfs to 30GB
pct resize 203 rootfs 30G

# 3. Start and configure
pct start 203

# 4. Start Tailscale daemon and authenticate
pct exec 203 -- systemctl start tailscaled
pct exec 203 -- systemctl enable tailscaled
pct exec 203 -- tailscale up
# Follow the URL printed to authorize in your browser

# 5. Create Worker-specific directories
pct exec 203 -- bash -c "
  mkdir -p /mnt/ktrdr-shared
  mkdir -p /opt/ktrdr-workers-d
"

# 6. Add DNS entry (add to your DNS server)
# workers-d.ktrdr.home.mynerd.place.   IN A    192.168.1.103

# 7. Copy docker-compose.workers.yml
scp docker-compose.workers.yml workers-d.ktrdr.home.mynerd.place:/opt/ktrdr-workers-d/

# 8. Deploy workers
ktrdr deploy workers D  # (requires updating CLI to support node D)

# 9. Verify
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

---

### Scaling Worker Replicas

**Scaling Strategy**: Profile-based scaling using docker-compose profiles

**Port Allocation**:

- backtest-worker-1: 5003 (default)
- backtest-worker-2: 5004 (scale-2)
- backtest-worker-3: 5007 (scale-3)
- training-worker-1: 5005 (default)
- training-worker-2: 5006 (scale-2)
- training-worker-3: 5008 (scale-3)

**Scale to 2 workers of each type**:

```bash
# SSH to worker LXC
ssh workers-b.ktrdr.home.mynerd.place
cd /opt/ktrdr-workers-b

# Deploy with scale-2 profile
docker compose --profile scale-2 up -d

# Verify workers registered
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

**Scale to 3 workers of each type**:

```bash
# Deploy with both scale-2 and scale-3 profiles
docker compose --profile scale-2 --profile scale-3 up -d

# Verify all 6 workers registered
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

**Scale back down to 1 of each**:

```bash
# Deploy with no profiles (default only)
docker compose up -d

# Removes scale-2 and scale-3 workers
```

**Note**: Prometheus config already includes all ports (5003-5008). Inactive workers show as DOWN in Prometheus UI.

---

### Updating Monitoring Dashboards

**v1 Approach**: Manual dashboard creation via Grafana UI. Pre-built dashboards planned for v2.

```bash
# Access Grafana UI
open http://grafana.ktrdr.home.mynerd.place:3000

# Create/edit dashboards manually
# Dashboards auto-save to Grafana volume
```

---

### Viewing Logs

```bash
# Backend logs
ssh backend.ktrdr.home.mynerd.place
docker logs -f ktrdr-backend

# Worker logs
ssh workers-b.ktrdr.home.mynerd.place
docker logs -f <container_id>  # Get ID from docker ps

# Database logs
ssh backend.ktrdr.home.mynerd.place
docker logs -f ktrdr-db
```

---

### System Health Check

**Run from Mac**:

```bash
# Check core services
ssh backend.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Check worker services
ssh workers-b.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'"
ssh workers-c.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Check worker registration
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq '.[] | {id:.worker_id, status:.status, type:.worker_type}'

# Check NFS mounts
ssh workers-b.ktrdr.home.mynerd.place "df -h | grep ktrdr-shared"
ssh workers-c.ktrdr.home.mynerd.place "df -h | grep ktrdr-shared"
```

---

## Troubleshooting

### Workers Not Registering

**Symptoms**: `curl /api/v1/workers` returns empty array

**Checks**:

1. Worker containers running: `ssh workers-b.ktrdr.home.mynerd.place "docker ps"`
2. Worker logs show registration attempt: `docker logs <container>`
3. DNS resolution works: `ssh workers-b.ktrdr.home.mynerd.place "dig backend.ktrdr.home.mynerd.place"`
4. Network connectivity: `ssh workers-b.ktrdr.home.mynerd.place "curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health"`
5. **Worker URL configuration**: Check `.env.workers` has correct `WORKER_PUBLIC_BASE_URL` (must be set, not auto-detected)

---

### NFS Mount Failures

**Symptoms**: `/mnt/ktrdr-shared` not accessible on workers

**Checks**:

1. NFS server running: `ssh backend.ktrdr.home.mynerd.place "docker ps | grep nfs"`
2. Export visible: `showmount -e backend.ktrdr.home.mynerd.place`
3. Mount attempt: `ssh workers-b.ktrdr.home.mynerd.place "mount -a"`
4. Check `/var/log/syslog` on worker LXC for NFS errors

---

### Database Connection Failures

**Symptoms**: Backend logs show "could not connect to database"

**Checks**:

1. PostgreSQL container running: `docker ps | grep ktrdr-db`
2. PostgreSQL health check: `docker exec ktrdr-db pg_isready -U ktrdr`
3. Backend can resolve db hostname: `docker exec ktrdr-backend ping db`
4. Check backend logs for connection string errors

---

## Related Documents

- [DESIGN.md](DESIGN.md) - Design decisions and rationale
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical specifications

---

**Document End**
