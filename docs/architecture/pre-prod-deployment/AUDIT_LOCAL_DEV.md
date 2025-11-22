# Audit: Current Docker Setup

**Date**: 2025-11-21
**Task**: 1.1 - Audit Current Docker Setup
**Branch**: update_local_dev_env

---

## Executive Summary

The current Docker setup is functional but fragmented across multiple files with inconsistent configurations. The `docker_dev.sh` wrapper adds complexity without providing clear value over direct `docker compose` commands. Key opportunities exist to consolidate and simplify.

---

## Current File Structure

```
docker/
├── docker-compose.yml          # Main dev config (271 lines)
├── docker-compose.dev.yml      # Distributed workers config (217 lines)
├── docker-compose.prod.yml     # Production config
├── docker-compose.research.yml # Research agent config
└── backend/
    ├── Dockerfile.dev
    └── Dockerfile (prod)

docker_dev.sh                   # Wrapper script (542 lines)
```

---

## Service Inventory

### docker/docker-compose.yml (Main Development)

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| backend | 8000 | FastAPI backend | ✅ Working |
| backtest-worker | 5003 | Single backtest worker | ✅ Working |
| frontend | 5173 | React frontend | ⚠️ Rarely used |
| mcp | host | Claude MCP server | ⚠️ Research profile |
| jaeger | 16686 | Distributed tracing | ✅ Working |
| prometheus | 9090 | Metrics collection | ✅ Working |
| grafana | 3000 | Dashboards | ✅ Working |

**Notable**: No PostgreSQL/TimescaleDB, only 1 backtest worker, no training workers

### docker/docker-compose.dev.yml (Distributed Workers)

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| backend | 8000 | Backend (duplicate) | ⚠️ Conflicts with main |
| backtest-worker | 5003 (dynamic) | Scalable workers | ✅ Working |
| training-worker | 5004 (dynamic) | Scalable workers | ✅ Working |
| jaeger | 16686 | Tracing (duplicate) | ⚠️ Duplicated |
| prometheus | 9090 | Metrics (duplicate) | ⚠️ Duplicated |
| grafana | 3000 | Dashboards (duplicate) | ⚠️ Duplicated |

**Notable**: Duplicate observability stack, uses `--scale` (causes port conflicts), deprecated env vars (`USE_TRAINING_HOST_SERVICE=false`)

---

## Pain Points Identified

### 1. **Fragmented Configuration** (High Priority)
- Two separate dev compose files with overlapping services
- No clear guidance on which file to use when
- Duplicate Jaeger, Prometheus, Grafana definitions

### 2. **No Database in Docker** (High Priority)
- PostgreSQL + TimescaleDB not included
- Prevents testing of DB-dependent features locally
- Inconsistent with pre-prod architecture

### 3. **Inconsistent Worker Configuration** (Medium Priority)
- Main compose: 1 backtest worker, no training workers
- Dev compose: uses `--scale` (port conflicts)
- Neither matches the design spec (2 backtest + 2 training with explicit ports)

### 4. **docker_dev.sh Adds Complexity** (Medium Priority)
- 542 lines of wrapper for commands that are simpler directly
- Mixes KTRDR and research agent commands
- Assumes working directory, complicates simple operations
- Outdated references (flake8 instead of ruff, python instead of uv)

### 5. **Hardcoded Values** (Medium Priority)
- `IB_HOST=172.17.0.1` - Docker bridge IP hardcoded
- Port numbers scattered throughout
- No `.env` file template for local secrets

### 6. **Deprecated Environment Variables** (Low Priority)
- `USE_TRAINING_HOST_SERVICE` and `USE_REMOTE_BACKTEST_SERVICE` still present
- WorkerRegistry is now the standard (no env flags needed)

### 7. **Missing Hot Reload for Workers** (Low Priority)
- Main compose: workers use `--reload` ✅
- Dev compose: uses array syntax `["uvicorn", ...]` which doesn't support reload

### 8. **version: "3.8" Deprecated** (Low Priority)
- docker-compose.dev.yml uses deprecated `version` key
- Modern Docker Compose doesn't need this

---

## What Works Well (Preserve)

### ✅ Volume Mounts for Hot Reload
```yaml
volumes:
  - ../ktrdr:/app/ktrdr
```
Bind-mounted code enables instant reload on changes.

### ✅ Health Checks
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```
Proper health checks for all services.

### ✅ Observability Stack Integration
```yaml
environment:
  - OTLP_ENDPOINT=http://jaeger:4317
```
Backend and workers properly configured to send traces to Jaeger.

### ✅ Network Isolation
```yaml
networks:
  - ktrdr-network
```
Single bridge network for all services.

### ✅ Named Volumes for Persistence
```yaml
volumes:
  pip-cache:
  uv-cache:
  prometheus_data:
  grafana_data:
```
Caches and data persist across restarts.

### ✅ depends_on with Conditions
```yaml
depends_on:
  jaeger:
    condition: service_healthy
```
Proper startup ordering with health conditions.

---

## What Needs to Change

### 1. Create Single `docker-compose.dev.yml` at Repo Root
- Consolidate all dev services into one file
- Move from `docker/` to repo root for simpler commands
- Include PostgreSQL + TimescaleDB

### 2. Add 4 Workers with Explicit Ports
- backtest-worker-1: 5003
- backtest-worker-2: 5004
- training-worker-1: 5005
- training-worker-2: 5006

### 3. Create `.env.dev.example` Template
- All required environment variables
- Sensible defaults for local development
- Clear comments explaining each

### 4. Deprecate docker_dev.sh
- Add deprecation notice
- Document direct docker compose commands
- Update CLAUDE.md

### 5. Remove Deprecated Environment Variables
- Remove `USE_TRAINING_HOST_SERVICE`
- Remove `USE_REMOTE_BACKTEST_SERVICE`
- Workers self-register via WorkerRegistry

### 6. Fix Command Syntax for Hot Reload
```yaml
# Use string command (supports --reload)
command: uvicorn ktrdr.backtesting.backtest_worker:app --host 0.0.0.0 --port 5003 --reload

# Not array syntax (doesn't support shell features)
command: ["uvicorn", "ktrdr.backtesting.backtest_worker:app", ...]
```

---

## Environment Variables to Document

### Required for All Services
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `JWT_SECRET`
- `OTLP_ENDPOINT`
- `KTRDR_API_URL`

### Worker-Specific
- `WORKER_PORT`
- `WORKER_PUBLIC_BASE_URL` (critical for self-registration)

### Observability
- `GF_ADMIN_PASSWORD` (Grafana)

---

## Recommendations Summary

| Priority | Action | Effort |
|----------|--------|--------|
| High | Create consolidated docker-compose.dev.yml | Medium |
| High | Add PostgreSQL + TimescaleDB | Low |
| High | Add 4 workers with explicit ports | Low |
| Medium | Create .env.dev.example | Low |
| Medium | Deprecate docker_dev.sh | Low |
| Medium | Update CLAUDE.md commands | Low |
| Low | Remove deprecated env vars | Trivial |
| Low | Remove version key | Trivial |

---

## Success Criteria Validation

- [x] Current Docker setup documented
- [x] Pain points identified (8 items)
- [x] Clear list of what to preserve vs. change

---

**Next Task**: Task 1.2 - Create docker-compose.dev.yml
