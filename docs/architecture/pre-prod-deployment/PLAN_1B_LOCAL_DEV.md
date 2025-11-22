# Project 1b: Local Dev Environment

**Status**: Ready for Implementation
**Estimated Effort**: Medium
**Prerequisites**: Project 1a (Dependencies & Dockerfile)

**Branch:** update_local_dev_env

---

## Goal

Streamlined, opinionated local development stack that starts with a single command and provides a complete working environment.

---

## Context

The current Docker setup uses `docker_dev.sh` wrapper script and may have inconsistent configurations. This project creates a clean `docker-compose.dev.yml` with PostgreSQL + TimescaleDB, multiple workers, and proper defaults.

---

## Tasks

### Task 1.1: Audit Current Docker Setup

**Goal**: Understand current state before refactoring

**Actions**:

1. Review existing `docker-compose*.yml` files
2. Review `docker_dev.sh` to understand what it does
3. Document current service configuration
4. Identify what works and what's "wobbly"
5. Note any hardcoded values that should be configurable

**Acceptance Criteria**:

- [ ] Current Docker setup documented
- [ ] Pain points identified
- [ ] Clear list of what to preserve vs. change

---

### Task 1.2: Create docker-compose.dev.yml

**File**: `docker-compose.dev.yml` (repository root)

**Goal**: Single compose file for local development

**Services to Include**:

- `db` - PostgreSQL 16 + TimescaleDB
- `backend` - KTRDR backend API (hot reload mode)
- `prometheus` - Metrics collection
- `grafana` - Dashboards
- `jaeger` - Distributed tracing
- `backtest-worker-1` - First backtest worker
- `backtest-worker-2` - Second backtest worker
- `training-worker-1` - First training worker
- `training-worker-2` - Second training worker

**Configuration Principles**:

- Hot reload by default (bind-mounted code)
- All services in single network
- Named volumes for persistence
- Health checks for db
- Sensible resource limits

**Actions**:

1. Create `docker-compose.dev.yml` with all services
2. Configure PostgreSQL with TimescaleDB extension
3. Configure backend with volume mounts for hot reload
4. Configure 4 workers (2 backtest, 2 training)
5. Configure observability stack
6. Add appropriate environment variables
7. Test complete stack startup

**Acceptance Criteria**:

- [ ] All 9 services defined
- [ ] PostgreSQL uses TimescaleDB image
- [ ] Backend has hot reload (code mounted, uvicorn --reload)
- [ ] Workers configured with unique ports (5003, 5004, 5005, 5006)
- [ ] All services on same network
- [ ] `docker compose -f docker-compose.dev.yml up` starts everything

---

### Task 1.3: Create .env.dev.example

**File**: `.env.dev.example` (repository root)

**Goal**: Template for local development secrets

**Actions**:

1. Create template with all required environment variables
2. Include sensible defaults for local dev
3. Add comments explaining each variable
4. Document which are secrets vs. configuration

**Content Structure**:

```bash
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=ktrdr
DB_USER=ktrdr
DB_PASSWORD=localdev  # Change in production

# Backend
JWT_SECRET=local-dev-secret-minimum-32-characters-long

# Grafana
GF_ADMIN_PASSWORD=admin

# Worker Configuration
KTRDR_API_URL=http://backend:8000

# Observability
OTLP_ENDPOINT=http://jaeger:4317
```

**Acceptance Criteria**:

- [ ] All required variables documented
- [ ] Sensible local dev defaults provided
- [ ] Clear comments explaining purpose
- [ ] Can copy to `.env.dev` and run immediately

---

### Task 1.4: Configure PostgreSQL + TimescaleDB

**Goal**: Database ready for time-series data

**Actions**:

1. Use `timescale/timescaledb:latest-pg16` image
2. Configure health check
3. Set up initialization scripts if needed
4. Configure volume for data persistence
5. Test TimescaleDB extension is available

**Docker Compose Config**:

```yaml
db:
  image: timescale/timescaledb:latest-pg16
  environment:
    POSTGRES_DB: ${DB_NAME:-ktrdr}
    POSTGRES_USER: ${DB_USER:-ktrdr}
    POSTGRES_PASSWORD: ${DB_PASSWORD:-localdev}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-ktrdr}"]
    interval: 10s
    timeout: 5s
    retries: 5
```

**Acceptance Criteria**:

- [ ] TimescaleDB image used
- [ ] Health check configured
- [ ] Data persists across restarts
- [ ] Can connect and verify TimescaleDB extension: `SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';`

---

### Task 1.5: Configure Workers with Unique Ports

**Goal**: Multiple workers running simultaneously

**Port Allocation**:

- backtest-worker-1: 5003
- backtest-worker-2: 5004
- training-worker-1: 5005
- training-worker-2: 5006

**Actions**:

1. Define each worker as separate service (not using --scale)
2. Configure unique WORKER_PORT for each
3. Configure WORKER_PUBLIC_BASE_URL for self-registration
4. Mount code for hot reload
5. Connect to backend and db

**Docker Compose Config** (example for one worker):

```yaml
backtest-worker-1:
  build:
    context: .
    dockerfile: docker/backend/Dockerfile
  command: uvicorn ktrdr.backtesting.backtest_worker:app --host 0.0.0.0 --port 5003 --reload
  volumes:
    - ./ktrdr:/app/ktrdr
  environment:
    WORKER_TYPE: backtesting
    WORKER_PORT: 5003
    WORKER_PUBLIC_BASE_URL: http://backtest-worker-1:5003
    KTRDR_API_URL: http://backend:8000
    DB_HOST: db
    # ... other env vars
  ports:
    - "5003:5003"
  depends_on:
    db:
      condition: service_healthy
    backend:
      condition: service_started
```

**Acceptance Criteria**:

- [ ] 4 workers defined (2 backtest, 2 training)
- [ ] Each has unique port
- [ ] Workers register with backend on startup
- [ ] Hot reload works for worker code changes

---

### Task 1.6: Configure Observability Stack

**Goal**: Prometheus, Grafana, and Jaeger working

**Actions**:

1. Configure Prometheus with appropriate scrape config
2. Configure Grafana with Prometheus and Jaeger datasources
3. Configure Jaeger with OTLP collector
4. Ensure backend and workers send traces to Jaeger
5. Use dev-appropriate retention (7 days for Prometheus)

**Acceptance Criteria**:

- [ ] Prometheus accessible at <http://localhost:9090>
- [ ] Grafana accessible at <http://localhost:3000>
- [ ] Jaeger accessible at <http://localhost:16686>
- [ ] Prometheus scrapes backend metrics
- [ ] Jaeger receives traces from backend

---

### Task 1.7: Create Prometheus Dev Config

**File**: `monitoring/prometheus-dev.yml`

**Goal**: Prometheus configuration for local development

**Actions**:

1. Create scrape config for local services (using Docker service names)
2. Configure scrape interval (15s)
3. Target backend and all workers

**Content**:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']

  - job_name: 'workers'
    static_configs:
      - targets:
        - 'backtest-worker-1:5003'
        - 'backtest-worker-2:5004'
        - 'training-worker-1:5005'
        - 'training-worker-2:5006'
```

**Acceptance Criteria**:

- [ ] Config created
- [ ] Prometheus loads config successfully
- [ ] All targets show as UP in Prometheus

---

### Task 1.8: Deprecate docker_dev.sh

**Goal**: Remove wrapper script in favor of direct commands

**Actions**:

1. Document current `docker_dev.sh` functionality
2. Create equivalent direct docker compose commands
3. Update documentation with new commands
4. Add deprecation notice to `docker_dev.sh`
5. Remove from CLAUDE.md recommendations

**New Commands to Document**:

```bash
# Start all services
docker compose -f docker-compose.dev.yml up

# Start in background
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Stop all services
docker compose -f docker-compose.dev.yml down

# Rebuild after Dockerfile changes
docker compose -f docker-compose.dev.yml build

# Restart specific service
docker compose -f docker-compose.dev.yml restart backend
```

**Acceptance Criteria**:

- [ ] All docker_dev.sh functionality available via direct commands
- [ ] docker_dev.sh marked as deprecated
- [ ] Documentation updated with new commands
- [ ] CLAUDE.md updated

---

### Task 1.9: Update .gitignore

**Goal**: Proper gitignore for local dev files

**Actions**:

1. Add `.env.dev` to .gitignore (contains secrets)
2. Keep `.env.dev.example` tracked
3. Add local volume directories if any
4. Add any other local dev artifacts

**Rules to Add**:

```gitignore
# Local development environment (contains secrets)
.env.dev

# Local development storage
dev-shared/
```

**Acceptance Criteria**:

- [ ] `.env.dev` ignored
- [ ] `.env.dev.example` tracked
- [ ] Cannot accidentally commit local secrets

---

### Task 1.10: Create Environment Validation Script

**File**: `scripts/validate-env.sh`

**Goal**: Validate required environment variables are set

**Actions**:

1. Create validation script
2. Check required variables for local dev
3. Provide clear error messages for missing variables
4. Make script executable

**Script**:

```bash
#!/bin/bash
# scripts/validate-env.sh

REQUIRED_DEV=(DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD JWT_SECRET)

check_vars() {
  local missing=()

  for var in "${REQUIRED_DEV[@]}"; do
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

# Source .env.dev if it exists
if [[ -f .env.dev ]]; then
  source .env.dev
fi

check_vars
```

**Acceptance Criteria**:

- [ ] Script created and executable
- [ ] Validates required variables
- [ ] Clear error messages for missing variables
- [ ] Returns proper exit codes

---

### Task 1.11: Update Documentation

**Goal**: Clear instructions for local development

**Actions**:

1. Update README with quick start using docker-compose.dev.yml
2. Update CLAUDE.md "Running the System" section
3. Document all services and their ports
4. Document common development workflows
5. Remove references to docker_dev.sh

**Documentation Sections**:

- Quick Start
- Service URLs (backend, grafana, jaeger, etc.)
- Common Commands
- Troubleshooting

**Acceptance Criteria**:

- [ ] README has clear quick start
- [ ] CLAUDE.md updated
- [ ] All service URLs documented
- [ ] Common commands documented

---

## Validation

**Final Verification**:

```bash
# 1. Copy environment template
cp .env.dev.example .env.dev

# 2. Start all services
docker compose -f docker-compose.dev.yml up -d

# 3. Wait for services to be ready
sleep 30

# 4. Check all services running
docker compose -f docker-compose.dev.yml ps

# 5. Verify backend
curl http://localhost:8000/api/v1/health

# 6. Verify Grafana
curl -s http://localhost:3000/api/health | jq

# 7. Verify Jaeger
curl -s http://localhost:16686/api/services | jq

# 8. Verify Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'

# 9. Check workers registered
curl http://localhost:8000/api/v1/workers | jq

# 10. Verify TimescaleDB
docker compose -f docker-compose.dev.yml exec db psql -U ktrdr -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"

# 11. Test hot reload (modify a file and check logs for reload)
```

---

## Success Criteria

- [ ] `docker compose -f docker-compose.dev.yml up` starts complete environment
- [ ] PostgreSQL + TimescaleDB working
- [ ] 4 workers running and registered
- [ ] Observability stack accessible
- [ ] Hot reload working for backend and workers
- [ ] Documentation clear and complete
- [ ] docker_dev.sh deprecated

---

## Dependencies

**Depends on**: Project 1a (Dependencies & Dockerfile)
**Blocks**: Project 2 (CI/CD & GHCR), Project 3 (Observability Dashboards)

---

## Notes

- Workers use explicit service definitions (not --scale) for predictable ports
- All services on same Docker network for simple service discovery
- Hot reload is default for fast iteration
- Secrets in .env.dev are acceptable for local development

---

**Previous Project**: [Project 1a: Dependencies & Dockerfile](PLAN_1A_DEPENDENCIES.md)
**Next Project**: [Project 2: CI/CD & GHCR](PLAN_2_CICD_GHCR.md)
