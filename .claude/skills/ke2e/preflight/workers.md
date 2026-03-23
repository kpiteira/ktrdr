# Pre-Flight: Workers

**Used by:** Worker E2E tests (M4 Configuration)
**Purpose:** Verify worker-specific prerequisites before test execution

---

## Checks

### 1. Worker Containers Running

**Command:**
```bash
docker compose ps --format "table {{.Name}}\t{{.State}}" | grep -E "(training-worker|backtest-worker)" | grep -v "exited"
```

**Pass if:** At least one training-worker and one backtest-worker container in running state

**Fail message:** "Worker containers not running"

---

### 2. Workers Registered with Backend

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

curl -s "http://localhost:$API_PORT/api/v1/workers" | \
  jq -e '.workers | length > 0' > /dev/null && echo "OK" || echo "NONE"
```

**Pass if:** At least one worker in the workers list

**Fail message:** "No workers registered with backend"

---

### 3. Worker Types Available

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

TRAINING=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training")] | length')
BACKTEST=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="backtest")] | length')

echo "Training workers: $TRAINING"
echo "Backtest workers: $BACKTEST"

[ "$TRAINING" -ge 1 ] && [ "$BACKTEST" -ge 1 ] && echo "OK" || echo "MISSING"
```

**Pass if:** At least one training worker AND at least one backtest worker

**Fail message:** "Missing worker type (need both training and backtest)"

---

### 4. Workers in Valid State

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

ERROR_WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | \
  jq '[.workers[] | select(.status=="error" or .status=="offline")] | length')

[ "$ERROR_WORKERS" -eq 0 ] && echo "OK" || echo "ERROR_STATE: $ERROR_WORKERS workers"
```

**Pass if:** No workers in error or offline state

**Fail message:** "Workers in error state - check worker logs"

---

## Quick Check Script

```bash
#!/bin/bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Pre-Flight: Workers ==="

# Check 1: Containers running
CONTAINER_COUNT=$(docker compose ps --format "table {{.Name}}" | grep -E "(training-worker|backtest-worker)" | wc -l | tr -d ' ')
if [ "$CONTAINER_COUNT" -lt 2 ]; then
  echo "FAIL: Less than 2 worker containers running (found $CONTAINER_COUNT)"
  docker compose ps | grep -E "(training-worker|backtest-worker)"
  exit 1
fi
echo "OK: $CONTAINER_COUNT worker containers running"

# Check 2: Workers registered
WORKER_COUNT=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '.workers | length')
if [ "$WORKER_COUNT" -eq 0 ]; then
  echo "FAIL: No workers registered with backend"
  exit 1
fi
echo "OK: $WORKER_COUNT workers registered"

# Check 3: Both types present
TRAINING=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training")] | length')
BACKTEST=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="backtest")] | length')
if [ "$TRAINING" -lt 1 ] || [ "$BACKTEST" -lt 1 ]; then
  echo "FAIL: Missing worker type (training=$TRAINING, backtest=$BACKTEST)"
  exit 1
fi
echo "OK: Both worker types available (training=$TRAINING, backtest=$BACKTEST)"

# Check 4: No error states
ERROR_WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | \
  jq '[.workers[] | select(.status=="error" or .status=="offline")] | length')
if [ "$ERROR_WORKERS" -gt 0 ]; then
  echo "WARN: $ERROR_WORKERS workers in error/offline state"
  curl -s "http://localhost:$API_PORT/api/v1/workers" | \
    jq '.workers[] | select(.status=="error" or .status=="offline") | {id: .worker_id, status: .status}'
fi

echo "=== Workers pre-flight passed ==="
```

---

## Symptom/Cure Mappings

### Worker Containers Not Running

**Symptom:** "Worker containers not running" or containers show "exited" status

**Cause:** Worker containers crashed or not started

**Cure:**
```bash
# Restart worker containers
[ -f .env.sandbox ] && source .env.sandbox
if [ -f .env.sandbox ]; then
  docker compose -f docker-compose.sandbox.yml up -d training-worker-1 backtest-worker-1
else
  docker compose up -d training-worker-1 backtest-worker-1
fi
```

**Max Retries:** 2
**Wait After Cure:** 15 seconds (worker startup + registration time)

---

### No Workers Registered

**Symptom:** "No workers registered with backend" or empty workers list

**Cause:** Workers not connecting to backend, or backend not accepting registrations

**Cure:**
```bash
# Check worker logs for connection issues
docker compose logs training-worker-1 --tail 30 2>&1 | grep -iE "(error|fail|connect|register)"

# Restart workers to trigger re-registration
docker compose restart training-worker-1 backtest-worker-1
```

**Max Retries:** 2
**Wait After Cure:** 20 seconds

---

### Missing Worker Type

**Symptom:** Only training or only backtest workers present

**Cause:** One worker type failed to start or register

**Cure:**
```bash
# Check which type is missing
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '.workers[] | {type, status}'

# Restart the missing type (example for backtest)
docker compose restart backtest-worker-1
```

**Max Retries:** 1
**Wait After Cure:** 15 seconds

---

### Workers in Error State

**Symptom:** Workers registered but with status "error" or "offline"

**Cause:** Worker startup validation failed, or worker crashed after registration

**Cure:**
```bash
# Check worker logs for error details
docker compose logs training-worker-1 --tail 50 2>&1 | grep -iE "(error|exception|fail|config)"

# If configuration error, fix config and restart
docker compose restart training-worker-1 backtest-worker-1
```

**Max Retries:** 1
**Wait After Cure:** 15 seconds

---

## Worker Configuration Reference

### Environment Variables (M4 Worker Settings)

| New Name (Preferred) | Deprecated Name | Default | Description |
|----------------------|-----------------|---------|-------------|
| KTRDR_WORKER_ID | WORKER_ID | auto-generated | Worker identifier |
| KTRDR_WORKER_PORT | WORKER_PORT | 5003 | Worker service port |
| KTRDR_WORKER_ENDPOINT_URL | WORKER_ENDPOINT_URL | auto-detected | Explicit endpoint URL |
| KTRDR_WORKER_PUBLIC_BASE_URL | WORKER_PUBLIC_BASE_URL | hostname | Public URL for distributed |

### Required Environment Variables

- `KTRDR_API_URL`: Backend API URL (required, no default)
  - Example: `http://backend:8000` (Docker) or `http://192.168.1.100:8000` (network)

### Port Allocation (docker-compose)

| Worker | Default Port |
|--------|--------------|
| backtest-worker-1 | 5003 |
| backtest-worker-2 | 5004 |
| training-worker-1 | 5005 |
| training-worker-2 | 5006 |
