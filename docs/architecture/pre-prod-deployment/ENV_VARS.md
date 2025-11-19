# Environment Variables Reference
## Pre-Production Deployment

**Version**: 1.0
**Date**: 2025-11-18

---

## Overview

This document provides comprehensive documentation for all environment variables required across KTRDR deployment environments. Variables are categorized by:

- **Sensitivity**: SECRET (must be protected) vs CONFIG (non-sensitive)
- **Scope**: Core stack, Worker stack, or Both
- **Required**: REQUIRED vs OPTIONAL

---

## ⚠️ Hybrid Configuration Model (No Secrets At Rest)

**IMPORTANT**: KTRDR uses a **hybrid configuration model** to keep secrets out of version control:

### Homelab Deployment (Proxmox LXCs)

**Configuration Split**:
- ✅ `.env.core` and `.env.workers` files contain **NON-SECRET** config (URLs, hostnames, ports)
- ✅ These files are **safe to commit** to git (no secrets)
- ✅ **Secrets only** (DB_PASSWORD, JWT_SECRET, etc.) stored in 1Password
- ✅ Deployment CLI fetches secrets via `op` CLI
- ✅ Secrets injected **inline** at deploy time (never written to disk)

**Deployment Flow**:
```bash
ktrdr deploy core backend
  ├─> Read non-secret config from .env.core on LXC
  ├─> Fetch secrets from 1Password (op CLI)
  ├─> SSH to backend.ktrdr.home.mynerd.place
  └─> docker compose up -d with inline secrets:
      DB_PASSWORD=... JWT_SECRET=... GF_ADMIN_PASSWORD=...
```

**On LXC Disk**:
- `.env.core` - Non-secret config (committed to git, copied to LXC)
- `.env.workers` - Non-secret config (committed to git, copied to LXC)
- No secret files - secrets only in Docker container config (in-memory)

### Local Development (Mac/Laptop)
- ✅ `.env.dev` file contains BOTH config AND secrets
- ✅ Copy [.env.dev.example](.env.dev.example) to `.env.dev`
- ✅ Fill in development values (simple passwords OK for local)
- ✅ `.env.dev` is in .gitignore (never committed)

**Key Difference**:
- **Homelab**: .env files (non-secret) + inline secrets (deploy-time)
- **Local Dev**: Single .env.dev file with everything (convenience)

---

## Core Stack Variables

### Database Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DB_HOST` | CONFIG | ✅ | `db` | PostgreSQL hostname (Docker service name in core stack) |
| `DB_PORT` | CONFIG | ✅ | `5432` | PostgreSQL port |
| `DB_NAME` | CONFIG | ✅ | `ktrdr` | Database name |
| `DB_USER` | SECRET | ✅ | - | Database username |
| `DB_PASSWORD` | SECRET | ✅ | - | Database password |

**Example (core stack)**:
```bash
DB_HOST=db
DB_PORT=5432
DB_NAME=ktrdr
DB_USER=ktrdr_user
DB_PASSWORD=<strong-secret-password>
```

---

### Backend API Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `JWT_SECRET` | SECRET | ✅ | - | Secret key for JWT token signing (min 32 chars) |
| `KTRDR_API_HOST` | CONFIG | ❌ | `0.0.0.0` | API server bind address |
| `KTRDR_API_PORT` | CONFIG | ❌ | `8000` | API server port |
| `ENVIRONMENT` | CONFIG | ❌ | `development` | Environment name (`development`, `homelab`, `production`) |
| `LOG_LEVEL` | CONFIG | ❌ | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `SHARED_MOUNT_PATH` | CONFIG | ✅ | `/mnt/shared` | Path to shared NFS storage inside container |

**Example**:
```bash
JWT_SECRET=<32-char-random-string>
KTRDR_API_HOST=0.0.0.0
KTRDR_API_PORT=8000
ENVIRONMENT=homelab
LOG_LEVEL=INFO
SHARED_MOUNT_PATH=/mnt/shared
```

**JWT_SECRET Generation**:
```bash
# Generate secure random string
openssl rand -base64 32
```

---

### Observability Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `OTLP_ENDPOINT` | CONFIG | ❌ | - | OpenTelemetry Protocol endpoint for traces (e.g., Jaeger) |
| `GF_ADMIN_PASSWORD` | SECRET | ✅ | - | Grafana admin password |
| `GF_AUTH_ANONYMOUS_ENABLED` | CONFIG | ❌ | `true` | Enable anonymous Grafana access (homelab only!) |
| `GF_AUTH_ANONYMOUS_ORG_ROLE` | CONFIG | ❌ | `Admin` | Role for anonymous users |

**Example**:
```bash
OTLP_ENDPOINT=http://jaeger:4317
GF_ADMIN_PASSWORD=<strong-grafana-password>
```

**Security Note**: Anonymous Grafana access should ONLY be enabled in isolated homelab environments. Disable for production.

---

### Container Registry Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `IMAGE_TAG` | CONFIG | ❌ | `latest` | Docker image tag to deploy (e.g., `sha-abc1234`) |

**Example**:
```bash
IMAGE_TAG=sha-a1b2c3d
```

**Tag Format**: `sha-<7-char-short-sha>` for git commit-based versioning

---

## Worker Stack Variables

### Worker Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `KTRDR_API_URL` | CONFIG | ✅ | - | Backend API base URL (e.g., `http://backend.ktrdr.home.mynerd.place:8000`) |
| `WORKER_TYPE` | CONFIG | ✅ | - | Worker type (`backtesting` or `training`) |
| `WORKER_PORT` | CONFIG | ✅ | - | Port worker listens on inside container |
| `WORKER_PUBLIC_BASE_URL` | CONFIG | ✅ | - | Externally accessible URL for this worker (MUST be set, not auto-detected) |
| `WORKER_HOSTNAME` | CONFIG | ✅ | - | Worker node hostname (e.g., `workers-b.ktrdr.home.mynerd.place`) |
| `SHARED_MOUNT_PATH` | CONFIG | ✅ | `/mnt/shared` | Path to shared NFS storage inside container |

**DNS Naming**: Uses `ktrdr.home.mynerd.place` pattern per [ktrdr-dns-naming.md](ktrdr-dns-naming.md)

**Example (backtest worker on node B)**:
```bash
KTRDR_API_URL=http://backend.ktrdr.home.mynerd.place:8000
WORKER_TYPE=backtesting
WORKER_PORT=5003
WORKER_PUBLIC_BASE_URL=http://workers-b.ktrdr.home.mynerd.place:5003
WORKER_HOSTNAME=workers-b.ktrdr.home.mynerd.place
SHARED_MOUNT_PATH=/mnt/shared
```

**Example (training worker on node C)**:
```bash
KTRDR_API_URL=http://backend.ktrdr.home.mynerd.place:8000
WORKER_TYPE=training
WORKER_PORT=5004
WORKER_PUBLIC_BASE_URL=http://workers-c.ktrdr.home.mynerd.place:5004
WORKER_HOSTNAME=workers-c.ktrdr.home.mynerd.place
SHARED_MOUNT_PATH=/mnt/shared
```

---

### Worker Database Access (Checkpointing)

Workers need database access for operation checkpointing:

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DB_HOST` | CONFIG | ✅ | - | PostgreSQL hostname (use `backend.ktrdr.home.mynerd.place` for workers) |
| `DB_PORT` | CONFIG | ✅ | `5432` | PostgreSQL port |
| `DB_NAME` | CONFIG | ✅ | `ktrdr` | Database name |
| `DB_USER` | SECRET | ✅ | - | Database username (same as core stack) |
| `DB_PASSWORD` | SECRET | ✅ | - | Database password (same as core stack) |

**Example (workers)**:
```bash
DB_HOST=backend.ktrdr.home.mynerd.place
DB_PORT=5432
DB_NAME=ktrdr
DB_USER=ktrdr_user
DB_PASSWORD=<same-password-as-core>
```

---

### Worker Observability

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `OTLP_ENDPOINT` | CONFIG | ❌ | - | OpenTelemetry endpoint for traces (use `http://backend.ktrdr.home.mynerd.place:4317`) |

**Example**:
```bash
OTLP_ENDPOINT=http://backend.ktrdr.home.mynerd.place:4317
```

---

## Local Development Variables

### Development-Specific

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `USE_HOT_RELOAD` | CONFIG | ❌ | `true` | Enable Uvicorn auto-reload for development |
| `DEV_MODE` | CONFIG | ❌ | `true` | Enable development features (verbose logging, etc.) |

**Example (.env.dev)**:
```bash
USE_HOT_RELOAD=true
DEV_MODE=true
```

---

## Deployment-Specific Variables (CLI)

These are used by the `ktrdr deploy` CLI command:

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `BACKTEST_WORKER_REPLICAS` | CONFIG | ❌ | `1` | Number of backtest worker replicas to deploy |
| `TRAINING_WORKER_REPLICAS` | CONFIG | ❌ | `1` | Number of training worker replicas to deploy |

**v1 Scope**: Single worker per type per node (`BACKTEST_WORKER_REPLICAS=1`, `TRAINING_WORKER_REPLICAS=1`)

**Future Enhancement**: Multi-replica scaling. See DESIGN.md "Future Enhancements".

---

## Validation Rules

### Required Variables by Environment

**Core Stack (Minimum)**:
```bash
DB_NAME=ktrdr
DB_USER=<secret>
DB_PASSWORD=<secret>
JWT_SECRET=<secret>
GF_ADMIN_PASSWORD=<secret>
```

**Worker Stack (Minimum)**:
```bash
KTRDR_API_URL=http://backend.ktrdr.home.mynerd.place:8000
WORKER_TYPE=backtesting  # or training
WORKER_PORT=5003         # or 5004
WORKER_PUBLIC_BASE_URL=http://workers-b.ktrdr.home.mynerd.place:5003
WORKER_HOSTNAME=workers-b.ktrdr.home.mynerd.place
DB_USER=<secret>
DB_PASSWORD=<secret>
```

---

## Security Guidelines

### Secrets Management

1. **Never commit secrets to git**
   - `.env.core` and `.env.workers` are in `.gitignore`
   - Use `.env.*.example` templates without real values

2. **Use 1Password for secret storage**
   - Store in vault: `KTRDR Homelab Secrets`
   - Item: `ktrdr-homelab-core`
   - Fields: `db_username`, `db_password`, `jwt_secret`, `grafana_password`

3. **Rotate secrets regularly**
   - Update 1Password
   - Redeploy services: `ktrdr deploy core all`

4. **Strong password requirements**
   - DB passwords: min 16 chars, mixed case, numbers, symbols
   - JWT secret: min 32 chars random
   - Grafana password: min 12 chars

---

## Troubleshooting

### Validation Script

Check if all required variables are set:

```bash
#!/bin/bash
# validate-env.sh

REQUIRED_CORE=(DB_NAME DB_USER DB_PASSWORD JWT_SECRET GF_ADMIN_PASSWORD)
REQUIRED_WORKERS=(KTRDR_API_URL WORKER_TYPE WORKER_PORT WORKER_PUBLIC_BASE_URL DB_USER DB_PASSWORD)

check_vars() {
  local -n vars=$1
  local missing=()

  for var in "${vars[@]}"; do
    if [[ -z "${!var}" ]]; then
      missing+=("$var")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "❌ Missing required variables: ${missing[*]}"
    return 1
  fi

  echo "✅ All required variables set"
  return 0
}

# Usage:
# source .env.core && check_vars REQUIRED_CORE
# source .env.workers && check_vars REQUIRED_WORKERS
```

---

## Environment-Specific Configurations

### Local Dev (Mac)

```bash
# .env.dev
DB_HOST=db
DB_PORT=5432
DB_NAME=ktrdr
DB_USER=ktrdr_dev
DB_PASSWORD=dev_password_change_me
JWT_SECRET=dev_jwt_secret_at_least_32_chars_long_12345
KTRDR_API_HOST=0.0.0.0
KTRDR_API_PORT=8000
ENVIRONMENT=development
LOG_LEVEL=DEBUG
GF_ADMIN_PASSWORD=admin
IMAGE_TAG=latest
```

### Homelab (Proxmox)

```bash
# Fetched from 1Password via ktrdr deploy CLI
DB_HOST=db  # (core) or backend.ktrdr.home.mynerd.place (workers)
DB_NAME=ktrdr
DB_USER=<from-1password>
DB_PASSWORD=<from-1password>
JWT_SECRET=<from-1password>
ENVIRONMENT=homelab
LOG_LEVEL=INFO
GF_ADMIN_PASSWORD=<from-1password>
IMAGE_TAG=sha-a1b2c3d  # From git commit

# Worker-specific (in .env.workers)
KTRDR_API_URL=http://backend.ktrdr.home.mynerd.place:8000
WORKER_HOSTNAME=workers-b.ktrdr.home.mynerd.place  # Node-specific
WORKER_PUBLIC_BASE_URL=http://workers-b.ktrdr.home.mynerd.place:5003
```

### Future Production (Azure)

```bash
# Fetched from Azure Key Vault
DB_HOST=<azure-postgres-fqdn>
DB_NAME=ktrdr
DB_USER=<from-keyvault>
DB_PASSWORD=<from-keyvault>
JWT_SECRET=<from-keyvault>
ENVIRONMENT=production
LOG_LEVEL=WARNING
OTLP_ENDPOINT=<azure-monitor-endpoint>
```

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical specifications
- [OPERATIONS.md](OPERATIONS.md) - Deployment procedures
- [ktrdr-dns-naming.md](ktrdr-dns-naming.md) - DNS naming strategy
- [.env.core](.env.core) - Core stack non-secret configuration (safe to commit)
- [.env.workers](.env.workers) - Worker stack non-secret configuration (safe to commit)
- [.env.dev.example](.env.dev.example) - Local development environment template
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Phased implementation tasks

---

**Document End**
