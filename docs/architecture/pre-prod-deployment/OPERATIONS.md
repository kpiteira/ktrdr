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

## LXC Provisioning

### Prerequisites

**Proxmox Cluster**:
- 3 Proxmox nodes on shared VLAN
- Access to Proxmox web UI or CLI
- Ubuntu 22.04 LTS template available

**Resources Available**:
- Node A: 4 cores, 16GB RAM
- Node B: 4 cores, 16GB RAM
- Node C: 4 cores, 8GB RAM

---

### Creating Core LXC (Node A)

```bash
# 1. Create LXC container
pct create 100 local:vztmpl/ubuntu-22.04-standard.tar.zst \
  --hostname ktrdr-core \
  --cores 3 \
  --memory 14336 \
  --swap 0 \
  --rootfs local-lvm:50 \
  --net0 name=eth0,bridge=vmbr0,ip=<IP>/24,gw=<GATEWAY> \
  --nameserver <DNS_SERVER> \
  --unprivileged 1

# 2. Start container
pct start 100

# 3. Install Docker
pct exec 100 -- bash -c "
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu jammy stable' | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
"

# 4. Create directory structure
pct exec 100 -- bash -c "
  mkdir -p /opt/ktrdr-core
  mkdir -p /srv/ktrdr-shared/{data,results,models,db-backups}
"

# 5. Configure SSH access
pct exec 100 -- bash -c "
  apt-get install -y openssh-server
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh
"

# Copy your SSH public key
cat ~/.ssh/id_rsa.pub | pct exec 100 -- bash -c "cat >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"
```

---

### Creating Worker LXC (Nodes B & C)

```bash
# Node B - Worker LXC
pct create 201 local:vztmpl/ubuntu-22.04-standard.tar.zst \
  --hostname ktrdr-workers-b \
  --cores 3 \
  --memory 14336 \
  --swap 0 \
  --rootfs local-lvm:30 \
  --net0 name=eth0,bridge=vmbr0,ip=<IP>/24,gw=<GATEWAY> \
  --nameserver <DNS_SERVER> \
  --unprivileged 1

pct start 201

# Install Docker (same as core LXC)
# Install SSH server (same as core LXC)
# Install NFS client
pct exec 201 -- apt-get install -y nfs-common

# Create mount point
pct exec 201 -- mkdir -p /mnt/ktrdr-shared

# Create directory structure
pct exec 201 -- mkdir -p /opt/ktrdr-workers-b

# Node C - Worker LXC (adjust RAM to 6GB)
pct create 202 local:vztmpl/ubuntu-22.04-standard.tar.zst \
  --hostname ktrdr-workers-c \
  --cores 3 \
  --memory 6144 \
  --swap 0 \
  --rootfs local-lvm:30 \
  --net0 name=eth0,bridge=vmbr0,ip=<IP>/24,gw=<GATEWAY> \
  --nameserver <DNS_SERVER> \
  --unprivileged 1

# Repeat Docker, SSH, NFS setup
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

**Example**: Add 4th worker node

```bash
# 1. Create new LXC on any Proxmox node
pct create 203 local:vztmpl/ubuntu-22.04-standard.tar.zst \
  --hostname ktrdr-workers-d \
  --cores 3 \
  --memory 14336 \
  --rootfs local-lvm:30 \
  --net0 name=eth0,bridge=vmbr0,ip=<IP>/24,gw=<GATEWAY>

# 2. Install Docker, SSH, NFS client (see Worker LXC provisioning)

# 3. Mount NFS share (see NFS Configuration)

# 4. Add DNS entry
# workers-d.ktrdr.home.mynerd.place.   IN A    <IP>

# 5. Copy docker-compose.workers.yml
scp docker-compose.workers.yml workers-d.ktrdr.home.mynerd.place:/opt/ktrdr-workers-d/

# 6. Deploy workers
ktrdr deploy workers D  # (requires updating CLI to support node D)

# 7. Verify
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
