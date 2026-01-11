# Pre-Flight: Common Checks

**Used by:** All E2E tests
**Purpose:** Verify basic environment is healthy before running any test

---

## Checks

### 1. Docker Healthy

**Command:**
```bash
docker compose ps --format "table {{.State}}" | grep -v "STATE" | grep -v "running" | wc -l
```

**Pass if:** Output is `0` (all containers running)

**Fail message:** "Docker containers not all running"

---

### 2. Backend API Responsive

**Command:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:${KTRDR_API_PORT:-8000}/api/v1/health
```

**Pass if:** Output is `200`

**Fail message:** "Backend API not responding"

---

### 3. Sandbox Detection

**Command:**
```bash
if [ -f .env.sandbox ]; then
  source .env.sandbox
  echo "Sandbox: KTRDR_API_PORT=$KTRDR_API_PORT"
else
  echo "Main environment: KTRDR_API_PORT=8000"
fi
```

**Pass if:** Runs without error, sets correct port

**Fail message:** "Unable to detect environment"

---

## Quick Check Script

Run all checks at once:

```bash
#!/bin/bash
set -e

# Load sandbox config if present
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Pre-Flight: Common Checks ==="

# Check 1: Docker
UNHEALTHY=$(docker compose ps --format "table {{.State}}" | grep -v "STATE" | grep -v "running" | wc -l | tr -d ' ')
if [ "$UNHEALTHY" -gt 0 ]; then
  echo "FAIL: Docker containers not all running"
  docker compose ps
  exit 1
fi
echo "OK: Docker healthy"

# Check 2: Backend API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$API_PORT/api/v1/health)
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Backend API not responding (HTTP $HTTP_CODE)"
  exit 1
fi
echo "OK: Backend API responding"

# Check 3: Environment
echo "OK: Using API_PORT=$API_PORT"

echo "=== All pre-flight checks passed ==="
```

---

## Symptom→Cure Mappings

### Docker Not Running

**Symptom:** "Docker containers not all running" or `docker compose ps` shows stopped containers

**Cause:** Docker daemon stopped, containers crashed, or compose not started

**Cure:**
```bash
# Recreate and restart Docker compose services (preserves volumes)
docker compose up -d --force-recreate
```

**Max Retries:** 2
**Wait After Cure:** 15 seconds (agent applies this wait after executing cure)

---

### Backend API Not Responding

**Symptom:** Health check returns non-200 or connection refused

**Cause:** Backend container not ready, crashed, or wrong port

**Cure:**
```bash
# Check if it's a port issue first
[ -f .env.sandbox ] && source .env.sandbox
export API_PORT=${KTRDR_API_PORT:-8000}
echo "Using API_PORT=$API_PORT"

# Start or restart backend (handles both stopped and removed containers)
docker compose up -d backend
```

**Max Retries:** 2
**Wait After Cure:** 10 seconds (agent applies this wait after executing cure)

---

### Wrong Port (Sandbox Issue)

**Symptom:** Connection refused on port 8000 but sandbox is active

**Cause:** .env.sandbox not loaded, using default port instead of sandbox port

**Cure:**
```bash
# Source sandbox config and export for subsequent commands
if [ -f .env.sandbox ]; then
  source .env.sandbox
  echo "Loaded sandbox config: KTRDR_API_PORT=$KTRDR_API_PORT"
  export API_PORT=$KTRDR_API_PORT
else
  echo "No sandbox detected, using default port 8000"
  export API_PORT=8000
fi
```

**Note:** This cure fixes the agent's port detection. The agent must re-source .env.sandbox before retrying the health check to use the correct port.

**Max Retries:** 1 (config issue — if this doesn't work, it's a real problem)
**Wait After Cure:** 0 seconds (config reload only, no service restart)
