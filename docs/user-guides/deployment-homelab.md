# KTRDR Homelab Deployment Guide

**Version**: 1.0
**Date**: 2025-11-25
**Audience**: Developers, DevOps, System Administrators
**Deployment Target**: Proxmox LXC Homelab with 1Password Secrets Management

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [1Password Configuration](#1password-configuration)
4. [First-Time Deployment](#first-time-deployment)
5. [Updating Deployments](#updating-deployments)
6. [Scaling Workers](#scaling-workers)
7. [Rollback Procedure](#rollback-procedure)
8. [Troubleshooting](#troubleshooting)
9. [Quick Reference](#quick-reference)

---

## Overview

This guide covers deploying KTRDR to a Proxmox homelab using the `ktrdr deploy` CLI commands. The deployment system features:

- **Secure secrets management** via 1Password (no secrets at rest)
- **One-command deployments** for core and worker services
- **Pre-deployment validation** to catch issues early
- **Dry-run mode** for safe testing
- **Profile-based worker scaling** (1-3 workers per type)

**Architecture Overview**:

```
┌──────────────────────────────────────────────────────────────────┐
│ Your Workstation (Mac/Linux)                                      │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ ktrdr deploy CLI                                            │  │
│ │   ↓                                                         │  │
│ │ 1Password CLI (op) ──→ Fetch secrets (in-memory only)      │  │
│ │   ↓                                                         │  │
│ │ SSH ──→ Remote execution with inline env vars              │  │
│ └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
         │
         │ SSH with inline secrets
         ↓
┌──────────────────────────────────────────────────────────────────┐
│ Proxmox Homelab                                                  │
│                                                                  │
│  ┌─────────────────────┐   ┌─────────────────────┐              │
│  │ Node A (Core LXC)   │   │ Node B (Worker LXC) │              │
│  │ • Backend API       │   │ • Backtest workers  │              │
│  │ • PostgreSQL        │   │ • Training workers  │              │
│  │ • Grafana           │   │                     │              │
│  │ • Jaeger            │   └─────────────────────┘              │
│  │ • NFS Server        │                                        │
│  └─────────────────────┘   ┌─────────────────────┐              │
│                             │ Node C (Worker LXC) │              │
│                             │ • Additional workers│              │
│                             └─────────────────────┘              │
└──────────────────────────────────────────────────────────────────┘
```

**Related Documentation**:

- [Proxmox LXC Deployment Guide](deployment-proxmox.md) - LXC provisioning and infrastructure setup
- [Docker Compose Deployment Guide](deployment.md) - Local development
- [Pre-prod Architecture](../architecture/pre-prod-deployment/ARCHITECTURE.md) - Technical specifications
- [Operations Manual](../architecture/pre-prod-deployment/OPERATIONS.md) - LXC provisioning, backups, DR

---

## Prerequisites

### 1. 1Password CLI (op)

The deployment CLI requires the 1Password CLI to fetch secrets securely.

**Install 1Password CLI**:

```bash
# macOS (Homebrew)
brew install --cask 1password/tap/1password-cli

# Linux
curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
  sudo gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] \
  https://downloads.1password.com/linux/debian/amd64 stable main" | \
  sudo tee /etc/apt/sources.list.d/1password.list
sudo apt update && sudo apt install 1password-cli
```

**Verify Installation**:

```bash
op --version
# Expected: 2.x.x or later
```

**Authenticate**:

```bash
# Sign in to your 1Password account
op signin

# Verify authentication
op account list
# Expected: Shows your account(s)
```

### 2. SSH Key Configuration

SSH keys must be configured for passwordless access to all LXC containers.

**Generate SSH Key** (if not already done):

```bash
ssh-keygen -t ed25519 -C "ktrdr-deploy"
```

**Copy SSH Key to LXCs**:

```bash
# Core LXC
ssh-copy-id root@backend.ktrdr.home.mynerd.place

# Worker LXCs
ssh-copy-id root@workers-b.ktrdr.home.mynerd.place
ssh-copy-id root@workers-c.ktrdr.home.mynerd.place
```

**Test SSH Connectivity**:

```bash
# Should connect without password prompt
ssh backend.ktrdr.home.mynerd.place "echo 'SSH working'"
ssh workers-b.ktrdr.home.mynerd.place "echo 'SSH working'"
ssh workers-c.ktrdr.home.mynerd.place "echo 'SSH working'"
```

**SSH Config** (optional, for convenience):

```bash
# ~/.ssh/config
Host backend.ktrdr.home.mynerd.place
    User root
    IdentityFile ~/.ssh/id_ed25519

Host workers-b.ktrdr.home.mynerd.place
    User root
    IdentityFile ~/.ssh/id_ed25519

Host workers-c.ktrdr.home.mynerd.place
    User root
    IdentityFile ~/.ssh/id_ed25519
```

### 3. Git Repository

You must run deployment commands from within the KTRDR git repository (for automatic SHA tagging).

```bash
# Verify you're in the repository
git rev-parse --short HEAD
# Expected: 7-character SHA (e.g., "a1b2c3d")
```

### 4. Docker on LXCs

Each LXC must have Docker installed. See [OPERATIONS.md](../architecture/pre-prod-deployment/OPERATIONS.md) for LXC provisioning.

**Verify Docker on LXCs**:

```bash
ssh backend.ktrdr.home.mynerd.place "docker --version"
ssh workers-b.ktrdr.home.mynerd.place "docker --version"
ssh workers-c.ktrdr.home.mynerd.place "docker --version"
```

### 5. GHCR Authentication

Workers pull images from GitHub Container Registry (GHCR), which requires authentication.

**Create GitHub PAT**:

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Generate new token with:
   - Name: `ktrdr-ghcr-read`
   - Repository access: Select `ktrdr` repository
   - Permissions: `read:packages`
3. Store token in 1Password (see next section)

---

## 1Password Configuration

### Vault Structure

Create a vault and item for KTRDR secrets:

**Vault**: `KTRDR Homelab Secrets`

**Item**: `ktrdr-homelab-core`

### Required Fields

| Field Label | Type | Description | Requirements |
|-------------|------|-------------|--------------|
| `db_username` | Password | Database username | e.g., `ktrdr` |
| `db_password` | Password | Database password | Strong, 20+ chars |
| `jwt_secret` | Password | JWT signing secret | Minimum 32 chars, random |
| `grafana_password` | Password | Grafana admin password | Strong, 16+ chars |
| `ghcr_token` | Password | GitHub PAT for GHCR | `read:packages` scope |

### Field Naming Conventions

- **Lowercase with underscores**: Use `db_password` not `DB_PASSWORD` or `dbPassword`
- **Type = Password**: All fields must be "Password" type (shows as CONCEALED in JSON)
- **Consistent labels**: Field labels should match the suffix of corresponding env vars

### Create Item via 1Password CLI

```bash
# Generate secure values first
JWT_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
DB_PASSWORD=$(openssl rand -base64 24)
GRAFANA_PASSWORD=$(openssl rand -base64 16)

# Create item
op item create \
  --category "Login" \
  --title "ktrdr-homelab-core" \
  --vault "KTRDR Homelab Secrets" \
  "db_username[password]=ktrdr" \
  "db_password[password]=$DB_PASSWORD" \
  "jwt_secret[password]=$JWT_SECRET" \
  "grafana_password[password]=$GRAFANA_PASSWORD" \
  "ghcr_token[password]=YOUR_GITHUB_PAT_HERE"

echo "Generated secrets (save these securely):"
echo "DB Password: $DB_PASSWORD"
echo "JWT Secret: $JWT_SECRET"
echo "Grafana Password: $GRAFANA_PASSWORD"
```

### Create Item via 1Password UI

1. Open 1Password → Create new vault "KTRDR Homelab Secrets"
2. Create new Login item named "ktrdr-homelab-core"
3. Add password fields (use "Add More" → "Password" for each):
   - `db_username`: `ktrdr`
   - `db_password`: Generate with `openssl rand -base64 24`
   - `jwt_secret`: Generate with `openssl rand -base64 32 | tr -d '/+=' | head -c 32`
   - `grafana_password`: Generate strong password
   - `ghcr_token`: Your GitHub PAT

### Verify 1Password Access

```bash
# Test item access
op item get ktrdr-homelab-core --format json | jq '.fields[] | {label: .label, type: .type}'

# Expected output (all should be CONCEALED):
# { "label": "db_username", "type": "CONCEALED" }
# { "label": "db_password", "type": "CONCEALED" }
# { "label": "jwt_secret", "type": "CONCEALED" }
# { "label": "grafana_password", "type": "CONCEALED" }
# { "label": "ghcr_token", "type": "CONCEALED" }

# Test fetching a specific value
op item get ktrdr-homelab-core --fields db_username
# Expected: ktrdr
```

---

## First-Time Deployment

### Step 1: Validate Prerequisites

Run a dry-run to validate all prerequisites:

```bash
# Validate core deployment prerequisites
ktrdr deploy core backend --dry-run

# Expected output:
# Validating prerequisites...
#   ✓ DNS resolution: backend.ktrdr.home.mynerd.place
#   ✓ SSH connectivity
#   ✓ Docker available on remote
#   ✓ 1Password CLI installed
#   ✓ 1Password authenticated
#   ✓ All prerequisites validated
# Fetching secrets from 1Password...
# Authenticating Docker to GHCR...
# [DRY RUN] Would execute on backend.ktrdr.home.mynerd.place:
#   cd /opt/ktrdr-core && DB_NAME='ktrdr' DB_USER='***' DB_PASSWORD='***' ...
```

### Step 2: Deploy Core Services

Deploy backend, database, and observability stack to the core LXC:

```bash
# Deploy all core services
ktrdr deploy core all

# Or deploy specific service
ktrdr deploy core backend
ktrdr deploy core db
```

**What happens**:

1. Fetches secrets from 1Password (in-memory only)
2. Authenticates Docker to GHCR on remote host
3. Gets current git SHA for image tag
4. SSHs to core LXC and executes:
   - `docker compose pull` (with inline env vars)
   - `docker compose up -d` (with inline env vars)
5. Reports success/failure

**Verify Core Deployment**:

```bash
# Check containers running
ssh backend.ktrdr.home.mynerd.place "docker ps"

# Expected containers:
# - ktrdr-backend
# - ktrdr-db
# - ktrdr-prometheus
# - ktrdr-grafana
# - ktrdr-jaeger

# Test backend API
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health | jq

# Access UIs
# - Backend API: http://backend.ktrdr.home.mynerd.place:8000/api/v1/docs
# - Grafana: http://grafana.ktrdr.home.mynerd.place:3000
# - Jaeger: http://backend.ktrdr.home.mynerd.place:16686
```

### Step 3: Deploy Workers

Deploy workers to each worker LXC:

```bash
# Deploy to Node B
ktrdr deploy workers B

# Deploy to Node C
ktrdr deploy workers C
```

**Verify Worker Deployment**:

```bash
# Check worker containers
ssh workers-b.ktrdr.home.mynerd.place "docker ps"
ssh workers-c.ktrdr.home.mynerd.place "docker ps"

# Verify workers registered with backend
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq

# Expected: Workers from both nodes listed with status "AVAILABLE"
```

### Step 4: End-to-End Verification

Run a test backtest to verify the full system:

```bash
# Start a test backtest
curl -X POST http://backend.ktrdr.home.mynerd.place:8000/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/models/neuro_mean_reversion/1d_v21",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-06-30"
  }' | jq

# Monitor progress
OPERATION_ID="<operation_id from response>"
watch -n 2 "curl -s http://backend.ktrdr.home.mynerd.place:8000/api/v1/operations/$OPERATION_ID | jq '.progress'"
```

---

## Updating Deployments

### Deploy New Code Version

After merging to `main` and CI builds new images:

```bash
# Deploy new version to core (uses current git SHA)
ktrdr deploy core all

# Deploy to workers
ktrdr deploy workers B
ktrdr deploy workers C

# Or deploy specific image tag
ktrdr deploy core backend --tag sha-abc1234
ktrdr deploy workers B --tag sha-abc1234
```

### Deploy with Custom Tag

```bash
# Use specific image tag (instead of auto-detecting from git)
ktrdr deploy core all --tag sha-fa8fe24

# Use 'latest' tag (not recommended for production)
ktrdr deploy core all --tag latest
```

### Skip Validation (Not Recommended)

```bash
# Skip pre-deployment checks (use with caution)
ktrdr deploy core all --skip-validation
```

### Deploy Without Executing (Dry Run)

```bash
# See exactly what would be executed without running it
ktrdr deploy core all --dry-run
ktrdr deploy workers B --dry-run
```

---

## Scaling Workers

### Profile-Based Scaling

Workers use Docker Compose profiles for scaling. Each node can run 1-3 workers of each type.

**Port Allocation**:

| Worker | Port | Profile | Always Running? |
|--------|------|---------|-----------------|
| backtest-worker-1 | 5003 | default | Yes |
| backtest-worker-2 | 5004 | scale-2 | No (profile) |
| backtest-worker-3 | 5007 | scale-3 | No (profile) |
| training-worker-1 | 5005 | default | Yes |
| training-worker-2 | 5006 | scale-2 | No (profile) |
| training-worker-3 | 5008 | scale-3 | No (profile) |

### Scale Up to 2 Workers Each

```bash
# Deploy with scale-2 profile
ktrdr deploy workers B --profile scale-2

# Verify 4 workers running (2 backtest + 2 training)
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq 'length'
```

### Scale Up to 3 Workers Each

```bash
# Deploy with both scale profiles
ktrdr deploy workers B --profile scale-2 --profile scale-3

# Verify 6 workers running (3 backtest + 3 training)
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | \
  jq 'group_by(.worker_type) | map({type: .[0].worker_type, count: length})'
```

### Scale Back Down

```bash
# Deploy without profiles (returns to 1 of each)
ktrdr deploy workers B

# Extra workers will stop; backend detects via health checks
```

### Check Worker Capacity

```bash
# View all workers by type and status
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | \
  jq '.[] | {worker_id, worker_type, status}'

# Count available workers
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers/health | jq
```

---

## Rollback Procedure

### Rollback to Previous Image Tag

If a deployment causes issues, rollback to the previous working image:

```bash
# 1. Find previous working tag
# Check GHCR: https://github.com/kpiteira/ktrdr2/pkgs/container/ktrdr-backend
# Or check git log: git log --oneline -10

# 2. Deploy previous tag
ktrdr deploy core all --tag sha-<previous-sha>
ktrdr deploy workers B --tag sha-<previous-sha>
ktrdr deploy workers C --tag sha-<previous-sha>

# 3. Verify rollback
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health | jq
```

### Rollback Database (If Needed)

If database schema changes caused issues:

```bash
# SSH to core LXC
ssh backend.ktrdr.home.mynerd.place

# List available backups
ls -la /srv/ktrdr-shared/db-backups/

# Restore from backup
BACKUP_FILE=/srv/ktrdr-shared/db-backups/ktrdr-20251125.sql.gz
gunzip < $BACKUP_FILE | docker exec -i ktrdr-db psql -U ktrdr ktrdr

# Restart backend
docker restart ktrdr-backend
```

---

## Troubleshooting

### Common Errors

#### "Not signed in to 1Password"

```bash
# Error:
# 1Password error: Not signed in to 1Password. Run: op signin

# Solution:
op signin
# Then retry deployment
```

#### "Item not found in 1Password"

```bash
# Error:
# 1Password error: Item 'ktrdr-homelab-core' not found in 1Password

# Diagnosis:
op vault list                                    # List vaults
op item list --vault "KTRDR Homelab Secrets"   # List items in vault

# Solution: Create the item (see 1Password Configuration section)
```

#### "SSH connection failed"

```bash
# Error:
# SSH error: Connection refused

# Diagnosis:
ssh backend.ktrdr.home.mynerd.place "echo test"  # Test SSH manually

# Common causes:
# 1. SSH key not copied to LXC
#    Solution: ssh-copy-id root@backend.ktrdr.home.mynerd.place
#
# 2. LXC not running
#    Solution: On Proxmox host: pct start 100
#
# 3. Network/DNS issues
#    Solution: Check DNS resolution: dig backend.ktrdr.home.mynerd.place
```

#### "DNS resolution failed"

```bash
# Error:
# Validation failed: DNS resolution failed for backend.ktrdr.home.mynerd.place

# Diagnosis:
dig backend.ktrdr.home.mynerd.place
ping backend.ktrdr.home.mynerd.place

# Solution: Add DNS entry to your DNS server or /etc/hosts
echo "192.168.1.10 backend.ktrdr.home.mynerd.place" | sudo tee -a /etc/hosts
```

#### "Docker login failed"

```bash
# Error:
# SSH error: Docker login failed

# Diagnosis:
ssh backend.ktrdr.home.mynerd.place "docker login ghcr.io -u YOUR_USERNAME --password-stdin"

# Common causes:
# 1. Invalid GHCR token
#    Solution: Generate new PAT with read:packages scope
#
# 2. Token expired
#    Solution: Generate new PAT, update in 1Password
```

#### "Docker not available on remote"

```bash
# Error:
# Validation failed: Docker not available on backend.ktrdr.home.mynerd.place

# Diagnosis:
ssh backend.ktrdr.home.mynerd.place "docker --version"

# Solution: Install Docker on LXC
# See: docs/architecture/pre-prod-deployment/OPERATIONS.md
```

#### "Workers not registering"

```bash
# Symptoms: Workers running but not in /api/v1/workers

# Diagnosis steps:
# 1. Check worker logs
ssh workers-b.ktrdr.home.mynerd.place "docker logs backtest-worker-1"

# 2. Check network connectivity
ssh workers-b.ktrdr.home.mynerd.place \
  "curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health"

# 3. Check WORKER_PUBLIC_BASE_URL in .env.workers
ssh workers-b.ktrdr.home.mynerd.place "cat /opt/ktrdr-workers-b/.env.workers"

# Common causes:
# 1. Wrong KTRDR_API_URL
# 2. Firewall blocking worker → backend
# 3. DNS resolution failing
# 4. WORKER_PUBLIC_BASE_URL not set (auto-detection fails in distributed setup)
```

### Debug Commands

```bash
# Check core services
ssh backend.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Check worker services
ssh workers-b.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# View backend logs
ssh backend.ktrdr.home.mynerd.place "docker logs ktrdr-backend --tail 100"

# View worker logs
ssh workers-b.ktrdr.home.mynerd.place "docker logs backtest-worker-1 --tail 100"

# Check worker registration
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | \
  jq '.[] | {id: .worker_id, status: .status, type: .worker_type}'

# Check NFS mounts on workers
ssh workers-b.ktrdr.home.mynerd.place "df -h | grep ktrdr-shared"

# System health overview
echo "=== Core Services ===" && \
ssh backend.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'" && \
echo "\n=== Worker B ===" && \
ssh workers-b.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'" && \
echo "\n=== Worker C ===" && \
ssh workers-c.ktrdr.home.mynerd.place "docker ps --format 'table {{.Names}}\t{{.Status}}'" && \
echo "\n=== Registered Workers ===" && \
curl -s http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | \
  jq '.[] | {id: .worker_id, status: .status}'
```

---

## Quick Reference

### CLI Commands

```bash
# Deploy core services
ktrdr deploy core all                    # Deploy all core services
ktrdr deploy core backend                # Deploy backend only
ktrdr deploy core db                     # Deploy database only

# Deploy workers
ktrdr deploy workers B                   # Deploy to node B
ktrdr deploy workers C                   # Deploy to node C

# Options (work with both core and workers)
--dry-run              # Show commands without executing
--tag <tag>            # Override image tag (default: current git SHA)
--skip-validation      # Skip prerequisite checks

# Worker scaling options
--profile scale-2      # Enable 2 workers of each type
--profile scale-3      # Enable 3 workers of each type (use with scale-2)
```

### Verification Commands

```bash
# Check backend health
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health | jq

# List registered workers
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq

# Worker health summary
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers/health | jq

# List running operations
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/operations | jq
```

### Service URLs

| Service | URL |
|---------|-----|
| Backend API | http://backend.ktrdr.home.mynerd.place:8000 |
| API Docs | http://backend.ktrdr.home.mynerd.place:8000/api/v1/docs |
| Grafana | http://grafana.ktrdr.home.mynerd.place:3000 |
| Jaeger UI | http://backend.ktrdr.home.mynerd.place:16686 |
| Prometheus | http://backend.ktrdr.home.mynerd.place:9090 (internal) |

### Emergency Procedures

```bash
# Restart all core services
ssh backend.ktrdr.home.mynerd.place "cd /opt/ktrdr-core && docker compose restart"

# Restart specific service
ssh backend.ktrdr.home.mynerd.place "docker restart ktrdr-backend"

# View live logs
ssh backend.ktrdr.home.mynerd.place "docker logs -f ktrdr-backend"

# Force redeploy (pull fresh images)
ktrdr deploy core all  # Always pulls latest for the tag
```

---

## Next Steps

- **Infrastructure Setup**: See [Proxmox Deployment Guide](deployment-proxmox.md) for LXC provisioning
- **Local Development**: See [Docker Compose Deployment](deployment.md)
- **Operations**: See [Operations Manual](../architecture/pre-prod-deployment/OPERATIONS.md)
- **Architecture**: See [Pre-prod Architecture](../architecture/pre-prod-deployment/ARCHITECTURE.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-25
