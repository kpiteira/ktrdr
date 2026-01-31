# Test: workers/startup-registration

**Purpose:** Validate that training and backtest workers start successfully, connect to the backend, and appear in the `/api/v1/workers` list with correct type and status

**Duration:** ~30 seconds (worker startup + registration timeout)

**Category:** Workers (M4 Configuration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox, API health

**Test-specific checks:**
- [ ] Docker containers for workers are running
- [ ] Backend API is responsive

**Worker container check:**
```bash
# Verify worker containers are running (not just started, but healthy)
docker compose ps --format "table {{.Name}}\t{{.State}}" | grep -E "(training-worker|backtest-worker)"
```

---

## Test Data

```json
{
  "expected_worker_types": ["training", "backtest"],
  "expected_statuses": ["idle", "busy"],
  "registration_timeout_seconds": 30
}
```

**Why this data:**
- Workers should register within 5-10 seconds of startup
- Extended timeout handles slow container initialization
- Both worker types should be present in properly configured environment

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Check worker containers running | Both training-worker and backtest-worker containers are up | container_status |
| 2 | Query workers API | Returns list with registered workers | workers_response |
| 3 | Validate worker types | Both training and backtest types present | worker_types_found |
| 4 | Validate worker status | All workers show idle or busy status | worker_statuses |

**Detailed Steps:**

### Step 1: Verify Worker Containers Running

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Check container status
WORKER_CONTAINERS=$(docker compose ps --format "json" | jq -s '[.[] | select(.Name | test("(training-worker|backtest-worker)"))]')
WORKER_COUNT=$(echo "$WORKER_CONTAINERS" | jq 'length')

echo "Worker containers found: $WORKER_COUNT"
echo "$WORKER_CONTAINERS" | jq '.[] | {name: .Name, state: .State}'
```

**Expected:**
- At least 1 training-worker container
- At least 1 backtest-worker container
- All containers in "running" state

**Capture:** Worker container names and states

### Step 2: Query Workers API

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Query workers endpoint
RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/workers")
echo "$RESPONSE" | jq '.'

# Extract worker list
WORKERS=$(echo "$RESPONSE" | jq -r '.workers')
WORKER_COUNT=$(echo "$WORKERS" | jq 'length')
echo "Registered workers: $WORKER_COUNT"
```

**Expected:**
- HTTP 200 response
- `workers` array in response
- At least 1 worker in the list

**Capture:** Full workers response, worker count

### Step 3: Validate Worker Types Present

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/workers")

# Check for training workers
TRAINING_WORKERS=$(echo "$RESPONSE" | jq '[.workers[] | select(.type == "training")] | length')
echo "Training workers: $TRAINING_WORKERS"

# Check for backtest workers
BACKTEST_WORKERS=$(echo "$RESPONSE" | jq '[.workers[] | select(.type == "backtest")] | length')
echo "Backtest workers: $BACKTEST_WORKERS"

# Verify both types present
if [ "$TRAINING_WORKERS" -ge 1 ] && [ "$BACKTEST_WORKERS" -ge 1 ]; then
  echo "PASS: Both worker types registered"
else
  echo "FAIL: Missing worker type(s)"
fi
```

**Expected:**
- At least 1 training worker
- At least 1 backtest worker

**Capture:** Count of each worker type

### Step 4: Validate Worker Status

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/workers")

# Check worker statuses (should be idle or busy, not error/offline)
echo "$RESPONSE" | jq '.workers[] | {id: .worker_id, type: .type, status: .status, endpoint: .endpoint_url}'

# Verify no workers in error state
ERROR_WORKERS=$(echo "$RESPONSE" | jq '[.workers[] | select(.status == "error")] | length')
if [ "$ERROR_WORKERS" -gt 0 ]; then
  echo "FAIL: $ERROR_WORKERS worker(s) in error state"
else
  echo "PASS: All workers in valid state"
fi
```

**Expected:**
- All workers have status "idle" or "busy"
- No workers in "error" or "offline" state
- Each worker has an endpoint_url

**Capture:** Worker details (id, type, status, endpoint)

---

## Success Criteria

All must pass for test to pass:

- [ ] At least 1 training-worker container is running
- [ ] At least 1 backtest-worker container is running
- [ ] Workers API returns 200 response
- [ ] At least 1 training worker registered in API response
- [ ] At least 1 backtest worker registered in API response
- [ ] All registered workers have status "idle" or "busy"
- [ ] All workers have valid endpoint_url

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Worker count > 0 | 0 workers fails | Workers not registering |
| Both types present | Missing type fails | Container not starting |
| Status is valid | "error"/"offline" fails | Registration problem |
| Endpoint URL format | Missing or malformed fails | Configuration issue |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| No workers in API response | ENVIRONMENT | Check worker container logs: `docker compose logs training-worker-1` |
| Container not running | ENVIRONMENT | Restart containers: `docker compose up -d training-worker-1 backtest-worker-1` |
| Workers in error state | CODE_BUG | Check worker startup validation, review WorkerSettings |
| Missing worker type | CONFIGURATION | Check docker-compose.yml includes both worker types |
| Endpoint URL invalid | CONFIGURATION | Check KTRDR_WORKER_PORT and WORKER_PUBLIC_BASE_URL env vars |

---

## Cleanup

None required - workers remain running for other tests.

---

## Troubleshooting

**If no workers registered:**
- **Cause:** Workers not connecting to backend
- **Check:** Worker logs for connection errors
- **Cure:** Verify KTRDR_API_URL is set correctly in worker containers

**If workers show error status:**
- **Cause:** Startup validation failing
- **Check:** `docker compose logs training-worker-1 2>&1 | head -50`
- **Cure:** Fix configuration issues shown in logs

**If endpoint URL is incorrect:**
- **Cause:** WORKER_PUBLIC_BASE_URL not set or misconfigured
- **Check:** Worker environment variables in docker-compose
- **Cure:** Ensure WORKER_PUBLIC_BASE_URL matches container network

---

## Evidence to Capture

- Container status: `docker compose ps` output
- Workers API response: Full JSON from `/api/v1/workers`
- Worker details: `{id, type, status, endpoint_url}` for each worker
- Any error logs from worker startup

---

## Notes

**Worker Registration Flow:**
1. Worker container starts
2. Worker calls `warn_deprecated_env_vars()` and `validate_all("worker")`
3. Worker registers with backend via `POST /api/v1/workers/register`
4. Backend adds worker to registry
5. Worker appears in `GET /api/v1/workers` response

**Port Note:** Workers use port 5003 as the canonical default (M4 fix for bug #4).
