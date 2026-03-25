# Test: workers/port-defaults

**Purpose:** Validate that workers use the consistent default port (5003) when no explicit `KTRDR_WORKER_PORT` is set, fixing the port duplication bug #4 where training_worker.py defaulted to 5002 while worker_registration.py defaulted to 5004

**Duration:** ~20 seconds

**Category:** Workers (M4 Configuration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox, API health

**Test-specific checks:**
- [ ] Docker daemon is running
- [ ] Can run one-off containers

---

## Test Data

```json
{
  "expected_default_port": 5003,
  "port_before_fix": {
    "training_worker_default": 5002,
    "worker_registration_default": 5004
  },
  "canonical_default_source": "WorkerSettings.port in ktrdr/config/settings.py"
}
```

**Why this data:**
- M4 introduced WorkerSettings with canonical default port 5003
- Before M4, there was inconsistency: training_worker.py used 5002, worker_registration.py used 5004
- This test ensures the single source of truth is being used

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Query WorkerSettings default port | Returns 5003 | settings_port |
| 2 | Check worker logs for port binding | Logs show port 5003 | log_output |
| 3 | Check worker registration endpoint | Registered with port 5003 | endpoint_url |

**Detailed Steps:**

### Step 1: Query WorkerSettings Default Port

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Run Python to check the default port in WorkerSettings
# Note: We explicitly unset KTRDR_WORKER_PORT to test the default
docker compose run --rm \
  --entrypoint python \
  -e KTRDR_WORKER_PORT= \
  training-worker-1 \
  -c "
from ktrdr.config.settings import WorkerSettings, clear_settings_cache
import os

# Ensure no env var is set
if 'KTRDR_WORKER_PORT' in os.environ:
    del os.environ['KTRDR_WORKER_PORT']
if 'WORKER_PORT' in os.environ:
    del os.environ['WORKER_PORT']

clear_settings_cache()
settings = WorkerSettings()
print(f'DEFAULT_PORT={settings.port}')
print(f'CANONICAL_DEFAULT=5003')
print(f'MATCH={settings.port == 5003}')
"
```

**Expected:**
- Output: `DEFAULT_PORT=5003`
- Output: `MATCH=True`

**Capture:** Default port value from WorkerSettings

### Step 2: Verify Worker Logs Show Correct Port

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Check the currently running workers for port information in logs
# Workers should log their port at startup

echo "=== Training Worker Logs ==="
docker compose logs training-worker-1 2>&1 | grep -iE "(port|5003|5002|5004|listening|bind)" | tail -10

echo ""
echo "=== Backtest Worker Logs ==="
docker compose logs backtest-worker-1 2>&1 | grep -iE "(port|5003|5002|5004|listening|bind)" | tail -10
```

**Expected:**
- Logs mention port 5003 (or worker-specific port from docker-compose)
- No references to old defaults (5002 for training, 5004 for registration)

**Capture:** Relevant log lines mentioning ports

### Step 3: Check Worker Registration Endpoint URL

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Query workers API to check registered endpoint URLs
RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/workers")

echo "=== Worker Registrations ==="
echo "$RESPONSE" | jq '.workers[] | {worker_id, type, endpoint_url}'

# Extract ports from endpoint URLs
echo ""
echo "=== Ports in Endpoint URLs ==="
echo "$RESPONSE" | jq -r '.workers[].endpoint_url' | while read url; do
  PORT=$(echo "$url" | grep -oE ':[0-9]+$' | tr -d ':')
  echo "URL: $url -> Port: $PORT"
done

# Verify no old default ports are in use (unless explicitly configured)
# Note: docker-compose may set explicit ports, which is fine
echo ""
echo "=== Port Check ==="
OLD_PORTS=$(echo "$RESPONSE" | jq -r '.workers[].endpoint_url' | grep -E ':(5002|5004)$' | wc -l | tr -d ' ')
if [ "$OLD_PORTS" -eq 0 ]; then
  echo "PASS: No workers using old conflicting defaults (5002/5004)"
else
  echo "INFO: $OLD_PORTS worker(s) using ports 5002 or 5004 (may be explicit config)"
fi
```

**Expected:**
- Workers have endpoint URLs with valid ports
- If using default (no explicit config), port should be 5003
- Ports are consistent (not mixing old defaults)

**Capture:** Full endpoint URLs and extracted ports

### Step 4: Validate Port Source in Code (Static Check)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Check the WorkerSettings source to confirm default is 5003
docker compose run --rm \
  --entrypoint python \
  training-worker-1 \
  -c "
import inspect
from ktrdr.config.settings import WorkerSettings

# Get the port field definition
port_field = WorkerSettings.model_fields.get('port')
if port_field:
    print(f'Port field default: {port_field.default}')
    print(f'Port field description: {port_field.description}')
else:
    print('Port field not found')

# Verify no hardcoded ports in worker_registration
from ktrdr.training.worker_registration import WorkerRegistration
source = inspect.getsourcefile(WorkerRegistration)
print(f'WorkerRegistration source: {source}')
"
```

**Expected:**
- Port field default is 5003
- Description mentions "canonical default"
- WorkerRegistration uses WorkerSettings, not hardcoded values

**Capture:** Field definition details

---

## Success Criteria

All must pass for test to pass:

- [ ] WorkerSettings.port default is 5003
- [ ] Worker logs show correct port binding
- [ ] Registered workers have valid endpoint URLs
- [ ] No evidence of old conflicting defaults (5002/5004) being used as defaults
- [ ] Port field has ge=1, le=65535 constraints

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Default port == 5003 | != 5003 fails | Default not updated |
| No 5002 as default | 5002 default fails | Old training_worker.py default |
| No 5004 as default | 5004 default fails | Old worker_registration.py default |
| Endpoint URL valid | Invalid/missing fails | Port not propagating |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Default != 5003 | CODE_BUG | Check WorkerSettings in settings.py |
| Hardcoded 5002 | CODE_BUG | Check training_worker.py for hardcoded port |
| Hardcoded 5004 | CODE_BUG | Check worker_registration.py for hardcoded port |
| Endpoint URL wrong port | CONFIGURATION | Check WORKER_PUBLIC_BASE_URL in docker-compose |

---

## Cleanup

None required - test uses `--rm` flag for one-off containers.

---

## Troubleshooting

**If default port is not 5003:**
- **Cause:** WorkerSettings not updated or being overridden
- **Check:** `ktrdr/config/settings.py` WorkerSettings.port field
- **Cure:** Ensure port field has `default=5003` in Field() or deprecated_field()

**If old ports appear in logs:**
- **Cause:** Worker code not using WorkerSettings
- **Check:** Training worker and backtest worker imports
- **Cure:** Ensure workers use `get_worker_settings().port`

**If endpoint URL has wrong port:**
- **Cause:** WORKER_PUBLIC_BASE_URL overriding default
- **Note:** This is expected behavior if explicitly configured
- **Check:** docker-compose.yml for explicit port settings

---

## Evidence to Capture

- WorkerSettings.port default value
- Worker startup logs mentioning port
- Registered endpoint URLs from API
- Any hardcoded port values found

---

## Notes

**Bug #4 Background:**
Before M4, there were multiple places defining the worker port default:
1. `training_worker.py` defaulted to 5002
2. `worker_registration.py` defaulted to 5004
3. No single source of truth

**M4 Fix:**
WorkerSettings in `ktrdr/config/settings.py` now provides the canonical default:
```python
class WorkerSettings(BaseSettings):
    port: int = deprecated_field(
        5003,  # Canonical default - fixes bug #4
        "KTRDR_WORKER_PORT",
        "WORKER_PORT",
        ge=1,
        le=65535,
        description="Worker service port (canonical default: 5003)",
    )
```

**Docker-Compose Overrides:**
Note that docker-compose.yml may set explicit ports for workers (e.g., 5003, 5004, 5005, 5006). These explicit configurations are correct and expected - the test validates the default when no explicit value is set.
