---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Compose File + Shared Data Setup

**Goal:** Developer can manually run two KTRDR stacks in parallel with shared data.

**Branch:** `feature/sandbox-m1-compose`

**Builds on:** Nothing (foundation milestone)

---

## E2E Test Scenario

**Purpose:** Prove parallel stacks work with manual commands before building CLI automation.

**Prerequisites:**
- Docker running
- Main ktrdr2 environment stopped (`docker compose down`)

```bash
# 1. Setup shared data directory
mkdir -p ~/.ktrdr/shared/{data,models,strategies}
cp -r ./data/* ~/.ktrdr/shared/data/ 2>/dev/null || true
cp -r ./models/* ~/.ktrdr/shared/models/ 2>/dev/null || true
cp -r ./strategies/* ~/.ktrdr/shared/strategies/ 2>/dev/null || true

# 2. Start first instance (slot 1)
export COMPOSE_PROJECT_NAME=ktrdr-test-1
export KTRDR_API_PORT=8001
export KTRDR_DB_PORT=5433
export KTRDR_GRAFANA_PORT=3001
export KTRDR_JAEGER_UI_PORT=16687
export KTRDR_JAEGER_OTLP_GRPC_PORT=4318
export KTRDR_JAEGER_OTLP_HTTP_PORT=4319
export KTRDR_PROMETHEUS_PORT=9091
export KTRDR_WORKER_PORT_1=5010
export KTRDR_WORKER_PORT_2=5011
export KTRDR_WORKER_PORT_3=5012
export KTRDR_WORKER_PORT_4=5013
export KTRDR_SHARED_DIR=~/.ktrdr/shared
docker compose -f docker-compose.sandbox.yml up -d

# 3. Wait for health
sleep 30
curl -f http://localhost:8001/api/v1/health  # Should return 200

# 4. Start second instance (slot 2) in another terminal
export COMPOSE_PROJECT_NAME=ktrdr-test-2
export KTRDR_API_PORT=8002
export KTRDR_DB_PORT=5434
export KTRDR_GRAFANA_PORT=3002
export KTRDR_JAEGER_UI_PORT=16688
export KTRDR_JAEGER_OTLP_GRPC_PORT=4319
export KTRDR_JAEGER_OTLP_HTTP_PORT=4320
export KTRDR_PROMETHEUS_PORT=9092
export KTRDR_WORKER_PORT_1=5020
export KTRDR_WORKER_PORT_2=5021
export KTRDR_WORKER_PORT_3=5022
export KTRDR_WORKER_PORT_4=5023
export KTRDR_SHARED_DIR=~/.ktrdr/shared
docker compose -f docker-compose.sandbox.yml up -d

# 5. Verify both running
curl -f http://localhost:8001/api/v1/health  # Instance 1
curl -f http://localhost:8002/api/v1/health  # Instance 2

# 6. Verify isolation - different databases
docker exec ktrdr-test-1-db-1 psql -U ktrdr -c "SELECT 'instance1'" # Should work
docker exec ktrdr-test-2-db-1 psql -U ktrdr -c "SELECT 'instance2'" # Should work

# 7. Cleanup
COMPOSE_PROJECT_NAME=ktrdr-test-1 docker compose -f docker-compose.sandbox.yml down -v
COMPOSE_PROJECT_NAME=ktrdr-test-2 docker compose -f docker-compose.sandbox.yml down -v
```

**Success Criteria:**
- [ ] Both health endpoints respond 200
- [ ] Each instance has its own database container
- [ ] No port conflicts during startup
- [ ] Shared data directory mounted in both instances

---

## Tasks

### Task 1.1: Create docker-compose.sandbox.yml

**File:** `docker-compose.sandbox.yml` (new)
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Configuration

**Description:**
Create a new compose file based on `docker-compose.yml` with parameterized ports for all services. This file will be used by sandbox instances during development. The main `docker-compose.yml` remains untouched.

**Implementation Notes:**

1. Copy `docker-compose.yml` to `docker-compose.sandbox.yml`
2. Parameterize all host-side ports with defaults matching current values:

```yaml
# Pattern: ${VAR:-default}:internal_port
ports:
  - "${KTRDR_API_PORT:-8000}:8000"
```

3. Add shared data mount with fallback:

```yaml
volumes:
  # Shared data (sandbox uses ~/.ktrdr/shared, default uses local ./data)
  - ${KTRDR_SHARED_DIR:-./data}:/app/data
  - ${KTRDR_SHARED_DIR:-./models}:/app/models
  - ${KTRDR_SHARED_DIR:-./strategies}:/app/strategies
```

4. For workers, parameterize both host port AND internal port (they must match):

```yaml
# Workers need matching internal/external ports for registration
ports:
  - "${KTRDR_WORKER_PORT_1:-5003}:${KTRDR_WORKER_PORT_1:-5003}"
environment:
  - WORKER_PORT=${KTRDR_WORKER_PORT_1:-5003}
```

**Ports to parameterize:**

| Service | Variable | Default |
|---------|----------|---------|
| db | `KTRDR_DB_PORT` | 5432 |
| backend | `KTRDR_API_PORT` | 8000 |
| jaeger UI | `KTRDR_JAEGER_UI_PORT` | 16686 |
| jaeger OTLP gRPC | `KTRDR_JAEGER_OTLP_GRPC_PORT` | 4317 |
| jaeger OTLP HTTP | `KTRDR_JAEGER_OTLP_HTTP_PORT` | 4318 |
| prometheus | `KTRDR_PROMETHEUS_PORT` | 9090 |
| grafana | `KTRDR_GRAFANA_PORT` | 3000 |
| backtest-worker-1 | `KTRDR_WORKER_PORT_1` | 5003 |
| backtest-worker-2 | `KTRDR_WORKER_PORT_2` | 5004 |
| training-worker-1 | `KTRDR_WORKER_PORT_3` | 5005 |
| training-worker-2 | `KTRDR_WORKER_PORT_4` | 5006 |

**Testing Requirements:**

*Unit Tests:* N/A (declarative config)

*Integration Tests:*
- [ ] Compose file validates: `docker compose -f docker-compose.sandbox.yml config`
- [ ] Default ports work: Start with no env vars, verify ports match current behavior

*Smoke Test:*
```bash
docker compose -f docker-compose.sandbox.yml config | grep -E "ports:" -A2
```

**Acceptance Criteria:**
- [ ] `docker-compose.sandbox.yml` exists at project root
- [ ] All 11 port mappings parameterized with correct defaults
- [ ] Shared data mounts use `${KTRDR_SHARED_DIR:-./path}` pattern
- [ ] Compose validates without errors
- [ ] Starting with no env vars produces identical behavior to current `docker-compose.yml`

---

### Task 1.2: Create Shared Data Directory Structure

**File:** `scripts/init-shared-data-dir.sh` (new)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Create a simple script that initializes the `~/.ktrdr/shared/` directory structure. This is a minimal version — the full `ktrdr sandbox init-shared` command comes in M5.

**Implementation Notes:**

```bash
#!/bin/bash
# scripts/init-shared-data-dir.sh
# Creates ~/.ktrdr/shared/ directory structure for sandbox instances

set -e

SHARED_DIR="${HOME}/.ktrdr/shared"

echo "Creating shared data directory: ${SHARED_DIR}"

mkdir -p "${SHARED_DIR}/data"
mkdir -p "${SHARED_DIR}/models"
mkdir -p "${SHARED_DIR}/strategies"

echo "Created:"
echo "  ${SHARED_DIR}/data/"
echo "  ${SHARED_DIR}/models/"
echo "  ${SHARED_DIR}/strategies/"
echo ""
echo "To populate with existing data:"
echo "  cp -r ./data/* ${SHARED_DIR}/data/"
echo "  cp -r ./models/* ${SHARED_DIR}/models/"
echo "  cp -r ./strategies/* ${SHARED_DIR}/strategies/"
```

**Testing Requirements:**

*Smoke Test:*
```bash
./scripts/init-shared-data-dir.sh
ls -la ~/.ktrdr/shared/
```

**Acceptance Criteria:**
- [ ] Script is executable (`chmod +x`)
- [ ] Creates all three subdirectories
- [ ] Idempotent (safe to run multiple times)
- [ ] Prints helpful output

---

### Task 1.3: Document Manual Multi-Instance Process

**File:** `docs/designs/Sandbox/MANUAL_TESTING.md` (new)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Document the manual process for running multiple instances. This serves as both documentation and a test script for M1 verification.

**Implementation Notes:**

Include:
1. Environment variable reference table (slot → ports)
2. Step-by-step commands for starting two instances
3. Verification commands
4. Cleanup commands
5. Troubleshooting (port conflicts, container name conflicts)

**Acceptance Criteria:**
- [ ] Document follows E2E test scenario format
- [ ] Port allocation table matches architecture doc
- [ ] Copy-pasteable commands

---

### Task 1.4: Verify Main Compose Unchanged

**File:** N/A (verification only)
**Type:** MIXED
**Estimated time:** 15 minutes

**Task Categories:** Configuration

**Description:**
Verify that the existing `docker-compose.yml` and `../ktrdr2` workflow are completely unaffected by M1 changes.

**Implementation Notes:**

```bash
# From ktrdr2 directory
cd ../ktrdr2
docker compose down -v  # Clean slate
docker compose up -d    # Start with main compose
sleep 30
curl -f http://localhost:8000/api/v1/health  # Must work
docker compose down
```

**Acceptance Criteria:**
- [ ] `docker-compose.yml` has zero changes
- [ ] `../ktrdr2` starts normally with `docker compose up`
- [ ] Default ports (8000, 5432, 3000, etc.) work
- [ ] No new files in ktrdr2 directory

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] `docker-compose.sandbox.yml` validates
- [ ] E2E test passes (two parallel instances)
- [ ] Main compose unchanged, ktrdr2 workflow works
- [ ] Quality gates pass: `make quality`

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| Two-File Strategy | Creates `docker-compose.sandbox.yml`, leaves main untouched |
| Internal ports fixed, external parameterized | Port mapping pattern `${VAR:-default}:fixed` |
| Shared data via `~/.ktrdr/shared/` | Mount pattern with fallback to `./data` |
| Pool-based port allocation | Documented port slots in manual testing doc |
