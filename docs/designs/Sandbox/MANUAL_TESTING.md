# Manual Multi-Instance Testing

This document describes how to manually run multiple KTRDR instances in parallel using `docker-compose.sandbox.yml`. Use this for M1 verification before CLI automation is available.

---

## Port Allocation Reference

Each sandbox slot uses offset ports to avoid conflicts:

| Service | Slot 0 (Main Dev) | Slot 1 | Slot 2 | Variable |
|---------|-------------------|--------|--------|----------|
| Backend API | 8000 | 8001 | 8002 | `KTRDR_API_PORT` |
| PostgreSQL | 5432 | 5433 | 5434 | `KTRDR_DB_PORT` |
| Grafana | 3000 | 3001 | 3002 | `KTRDR_GRAFANA_PORT` |
| Jaeger UI | 16686 | 16687 | 16688 | `KTRDR_JAEGER_UI_PORT` |
| Jaeger OTLP gRPC | 4317 | 4327 | 4337 | `KTRDR_JAEGER_OTLP_GRPC_PORT` |
| Jaeger OTLP HTTP | 4318 | 4328 | 4338 | `KTRDR_JAEGER_OTLP_HTTP_PORT` |
| Prometheus | 9090 | 9091 | 9092 | `KTRDR_PROMETHEUS_PORT` |
| Backtest Worker 1 | 5003 | 5010 | 5020 | `KTRDR_WORKER_PORT_1` |
| Backtest Worker 2 | 5004 | 5011 | 5021 | `KTRDR_WORKER_PORT_2` |
| Training Worker 1 | 5005 | 5012 | 5022 | `KTRDR_WORKER_PORT_3` |
| Training Worker 2 | 5006 | 5013 | 5023 | `KTRDR_WORKER_PORT_4` |

**Note:** Slot 0 is reserved for the main development environment (`docker-compose.yml`). Sandbox instances use slots 1-10.

---

## Prerequisites

- Docker running
- Main ktrdr2 environment stopped: `docker compose down`
- Shared data directory initialized (see Step 1)

---

## E2E Test Scenario

**Purpose:** Prove parallel stacks work with manual commands before building CLI automation.

### Step 1: Setup Shared Data Directory

```bash
# Initialize shared data directory structure
./scripts/init-shared-data-dir.sh

# Optionally populate with existing data
cp -r ./data/* ~/.ktrdr/shared/data/ 2>/dev/null || true
cp -r ./models/* ~/.ktrdr/shared/models/ 2>/dev/null || true
cp -r ./strategies/* ~/.ktrdr/shared/strategies/ 2>/dev/null || true
```

### Step 2: Start First Instance (Slot 1)

```bash
# Set project name for container isolation
export COMPOSE_PROJECT_NAME=ktrdr-test-1

# Set ports for slot 1
export KTRDR_API_PORT=8001
export KTRDR_DB_PORT=5433
export KTRDR_GRAFANA_PORT=3001
export KTRDR_JAEGER_UI_PORT=16687
export KTRDR_JAEGER_OTLP_GRPC_PORT=4327
export KTRDR_JAEGER_OTLP_HTTP_PORT=4328
export KTRDR_PROMETHEUS_PORT=9091
export KTRDR_WORKER_PORT_1=5010
export KTRDR_WORKER_PORT_2=5011
export KTRDR_WORKER_PORT_3=5012
export KTRDR_WORKER_PORT_4=5013

# Set shared data directories
export KTRDR_DATA_DIR=${HOME}/.ktrdr/shared/data
export KTRDR_MODELS_DIR=${HOME}/.ktrdr/shared/models
export KTRDR_STRATEGIES_DIR=${HOME}/.ktrdr/shared/strategies

# Start the stack
docker compose -f docker-compose.sandbox.yml up -d
```

### Step 3: Wait for Health

```bash
# Wait for services to start
sleep 30

# Verify instance 1 is healthy
curl -f http://localhost:8001/api/v1/health
# Should return: {"status":"healthy",...}
```

### Step 4: Start Second Instance (Slot 2)

Open a **new terminal** and run:

```bash
# Set project name for container isolation
export COMPOSE_PROJECT_NAME=ktrdr-test-2

# Set ports for slot 2
export KTRDR_API_PORT=8002
export KTRDR_DB_PORT=5434
export KTRDR_GRAFANA_PORT=3002
export KTRDR_JAEGER_UI_PORT=16688
export KTRDR_JAEGER_OTLP_GRPC_PORT=4337
export KTRDR_JAEGER_OTLP_HTTP_PORT=4338
export KTRDR_PROMETHEUS_PORT=9092
export KTRDR_WORKER_PORT_1=5020
export KTRDR_WORKER_PORT_2=5021
export KTRDR_WORKER_PORT_3=5022
export KTRDR_WORKER_PORT_4=5023

# Set shared data directories
export KTRDR_DATA_DIR=${HOME}/.ktrdr/shared/data
export KTRDR_MODELS_DIR=${HOME}/.ktrdr/shared/models
export KTRDR_STRATEGIES_DIR=${HOME}/.ktrdr/shared/strategies

# Start the stack
docker compose -f docker-compose.sandbox.yml up -d
```

### Step 5: Verify Both Running

```bash
# Check instance 1
curl -f http://localhost:8001/api/v1/health

# Check instance 2
curl -f http://localhost:8002/api/v1/health
```

### Step 6: Verify Isolation

```bash
# Each instance has its own database
docker exec ktrdr-test-1-db-1 psql -U ktrdr -c "SELECT 'instance1'"
docker exec ktrdr-test-2-db-1 psql -U ktrdr -c "SELECT 'instance2'"

# List all running containers
docker ps --filter "name=ktrdr-test" --format "table {{.Names}}\t{{.Ports}}"
```

### Step 7: Cleanup

```bash
# Stop and remove instance 1
COMPOSE_PROJECT_NAME=ktrdr-test-1 docker compose -f docker-compose.sandbox.yml down -v

# Stop and remove instance 2
COMPOSE_PROJECT_NAME=ktrdr-test-2 docker compose -f docker-compose.sandbox.yml down -v
```

---

## Success Criteria

- [ ] Both health endpoints respond 200
- [ ] Each instance has its own database container
- [ ] No port conflicts during startup
- [ ] Shared data directory mounted in both instances

---

## Troubleshooting

### Port Conflicts

**Symptom:** `Error starting userland proxy: listen tcp4 0.0.0.0:XXXX: bind: address already in use`

**Solution:**
1. Check what's using the port: `lsof -i :XXXX`
2. Either stop the conflicting service or choose a different slot
3. If main dev environment is running, stop it: `docker compose down`

### Container Name Conflicts

**Symptom:** `container name "/ktrdr-test-X-backend-1" is already in use`

**Solution:**
1. Remove orphaned containers: `docker compose -f docker-compose.sandbox.yml down --remove-orphans`
2. Or remove specific container: `docker rm -f <container_name>`

### Shared Data Not Visible

**Symptom:** Data files not appearing in container

**Solution:**
1. Verify directories exist: `ls -la ~/.ktrdr/shared/`
2. Check volume mounts: `docker inspect <container> | grep -A 10 Mounts`
3. Ensure `KTRDR_DATA_DIR`, `KTRDR_MODELS_DIR`, `KTRDR_STRATEGIES_DIR` are set correctly

### Workers Not Registering

**Symptom:** Workers don't appear in `/api/v1/workers` response

**Solution:**
1. Verify worker ports match: `KTRDR_WORKER_PORT_X` must be set for each worker
2. Check worker logs: `docker compose -f docker-compose.sandbox.yml logs backtest-worker-1`
3. Workers need matching internal/external ports for registration
