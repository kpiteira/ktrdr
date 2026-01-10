# Pre-Flight: Common Checks

**Used by:** All E2E tests
**Purpose:** Verify basic environment is healthy before running any test

---

## Checks

### 1. Docker Healthy

**Command:**
```bash
docker compose ps --format json | jq -r '.[].State' | grep -v "running" | wc -l
```

**Pass if:** Output is `0` (all containers running)

**Fail message:** "Docker containers not all running"

---

### 2. Backend API Responsive

**Command:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:${API_PORT:-8000}/health
```

**Pass if:** Output is `200`

**Fail message:** "Backend API not responding"

---

### 3. Sandbox Detection

**Command:**
```bash
if [ -f .env.sandbox ]; then
  source .env.sandbox
  echo "Sandbox: API_PORT=$API_PORT"
else
  echo "Main environment: API_PORT=8000"
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
API_PORT=${API_PORT:-8000}

echo "=== Pre-Flight: Common Checks ==="

# Check 1: Docker
UNHEALTHY=$(docker compose ps --format json | jq -r '.[].State' | grep -v "running" | wc -l)
if [ "$UNHEALTHY" -gt 0 ]; then
  echo "FAIL: Docker containers not all running"
  docker compose ps
  exit 1
fi
echo "OK: Docker healthy"

# Check 2: Backend API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$API_PORT/health)
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

*(Cures will be added in Milestone 3)*

| Symptom | Cause | Cure |
|---------|-------|------|
| Docker containers not running | Docker stopped or crashed | TBD (M3) |
| Backend API not responding | Container starting or crashed | TBD (M3) |
| Wrong port | Sandbox detection failed | TBD (M3) |
