# Test: workers/config-validation

**Purpose:** Validate that worker startup validation works correctly - invalid configuration (e.g., `KTRDR_WORKER_PORT=abc`) causes immediate worker exit with code 1

**Duration:** ~15 seconds (container start + immediate exit)

**Category:** Workers (M4 Configuration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox detection

**Test-specific checks:**
- [ ] Docker daemon is running
- [ ] Access to docker-compose configuration

**Note:** This test temporarily modifies worker configuration to test validation failure. The test runs a separate container instance with invalid config rather than modifying the main workers.

---

## Test Data

```json
{
  "invalid_configs": [
    {"env_var": "KTRDR_WORKER_PORT", "invalid_value": "abc", "description": "non-numeric port"},
    {"env_var": "KTRDR_WORKER_PORT", "invalid_value": "-1", "description": "negative port"},
    {"env_var": "KTRDR_WORKER_PORT", "invalid_value": "99999", "description": "port out of range"}
  ],
  "expected_exit_code": 1,
  "timeout_seconds": 30
}
```

**Why this data:**
- Tests Pydantic validation for WorkerSettings.port field
- Port must be between 1 and 65535 (per `ge=1, le=65535` constraint)
- Worker should fail fast with exit code 1, not hang

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Run worker with invalid port (non-numeric) | Container exits immediately | exit_code, logs |
| 2 | Verify exit code is 1 | Exit code = 1 | container_exit_code |
| 3 | Check logs for validation error | Error message mentions "port" | error_message |
| 4 | (Optional) Test other invalid values | Same behavior | additional_test_results |

**Detailed Steps:**

### Step 1: Run Worker with Invalid Port Configuration

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Run a one-off worker container with invalid port
# Using docker run directly to capture exit code and logs

# Get the image name from docker-compose
WORKER_IMAGE=$(docker compose config --images | grep -E "(ktrdr.*worker|worker)" | head -1)
if [ -z "$WORKER_IMAGE" ]; then
  WORKER_IMAGE="ktrdr-backend:latest"  # fallback
fi

echo "Using image: $WORKER_IMAGE"

# Run with invalid port (non-numeric string)
docker run --rm \
  -e KTRDR_WORKER_PORT=abc \
  -e KTRDR_API_URL=http://backend:8000 \
  -e KTRDR_DB_HOST=db \
  -e KTRDR_DB_PASSWORD=localdev \
  --network=$(docker network ls --filter name=ktrdr --format "{{.Name}}" | head -1) \
  --entrypoint python \
  "$WORKER_IMAGE" \
  -c "from ktrdr.config import validate_all; validate_all('worker')" \
  2>&1

# Capture exit code
EXIT_CODE=$?
echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Container runs briefly then exits
- Exit code is 1 (configuration error)
- Logs show validation error about port

**Capture:** Exit code, full log output

### Step 2: Verify Exit Code Is 1

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Alternative approach using docker-compose run
docker compose run --rm \
  -e KTRDR_WORKER_PORT=abc \
  training-worker-1 \
  python -c "from ktrdr.config import validate_all; validate_all('worker')" \
  2>&1

EXIT_CODE=$?
echo "Exit code: $EXIT_CODE"

if [ "$EXIT_CODE" -eq 1 ]; then
  echo "PASS: Worker exited with code 1 as expected"
else
  echo "FAIL: Worker exited with code $EXIT_CODE, expected 1"
fi
```

**Expected:**
- Exit code = 1

**Capture:** Exit code value

### Step 3: Check Logs for Validation Error

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Run and capture output
OUTPUT=$(docker compose run --rm \
  -e KTRDR_WORKER_PORT=abc \
  training-worker-1 \
  python -c "from ktrdr.config import validate_all; validate_all('worker')" \
  2>&1)

echo "$OUTPUT"

# Check for validation error message
if echo "$OUTPUT" | grep -iE "(port|validation|invalid|error)" > /dev/null; then
  echo "PASS: Error message mentions validation issue"
else
  echo "FAIL: Error message does not mention validation issue"
fi

# Specifically check for Pydantic validation error format
if echo "$OUTPUT" | grep -iE "(input should be a valid integer|value is not a valid integer)" > /dev/null; then
  echo "PASS: Pydantic validation error detected"
fi
```

**Expected:**
- Output contains error message mentioning "port" or "validation"
- Error message is human-readable
- Points to the configuration issue

**Capture:** Full error output, key error phrases

### Step 4: Test Additional Invalid Values (Optional)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

echo "=== Testing negative port (-1) ==="
docker compose run --rm \
  -e KTRDR_WORKER_PORT=-1 \
  training-worker-1 \
  python -c "from ktrdr.config import validate_all; validate_all('worker')" \
  2>&1
NEGATIVE_EXIT=$?
echo "Exit code: $NEGATIVE_EXIT"

echo ""
echo "=== Testing out-of-range port (99999) ==="
docker compose run --rm \
  -e KTRDR_WORKER_PORT=99999 \
  training-worker-1 \
  python -c "from ktrdr.config import validate_all; validate_all('worker')" \
  2>&1
RANGE_EXIT=$?
echo "Exit code: $RANGE_EXIT"

# Verify both fail correctly
if [ "$NEGATIVE_EXIT" -eq 1 ] && [ "$RANGE_EXIT" -eq 1 ]; then
  echo "PASS: All invalid port values cause exit code 1"
else
  echo "FAIL: Some invalid values did not cause exit code 1"
fi
```

**Expected:**
- All invalid port values cause exit code 1
- Error messages are specific to the validation failure

**Capture:** Exit codes for each test case

---

## Success Criteria

All must pass for test to pass:

- [ ] Worker with `KTRDR_WORKER_PORT=abc` exits with code 1
- [ ] Worker with `KTRDR_WORKER_PORT=-1` exits with code 1
- [ ] Worker with `KTRDR_WORKER_PORT=99999` exits with code 1
- [ ] Exit happens within 30 seconds (fail-fast behavior)
- [ ] Error output contains validation error message
- [ ] Error message mentions "port" or field name

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Exit code == 1 | Any other code fails | Validation not raising ConfigurationError |
| Startup time < 30s | > 30s fails | Worker hanging, not fail-fast |
| Error in output | No error fails | Silent failure, not logging |
| Message clarity | Vague error fails | Poor error messaging |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Exit code 0 | CODE_BUG | Check validate_all() is called at worker startup |
| Exit code != 1 | CODE_BUG | Check exception handling in worker entrypoint |
| No error output | CODE_BUG | Check logging configuration in worker |
| Timeout (hangs) | CODE_BUG | Check if validation is being bypassed |
| Container not found | ENVIRONMENT | Rebuild containers: `docker compose build` |

---

## Cleanup

None required - test uses `--rm` flag to auto-remove test containers.

---

## Troubleshooting

**If exit code is 0:**
- **Cause:** Validation not being called or not failing
- **Check:** Verify `validate_all("worker")` is in worker startup code
- **File:** `ktrdr/backtesting/backtest_worker.py` lines 39-40

**If worker hangs:**
- **Cause:** Validation bypassed, worker trying to run normally
- **Check:** Environment variable is being passed correctly
- **Cure:** Ensure `-e KTRDR_WORKER_PORT=abc` is in docker run command

**If no error message:**
- **Cause:** Logging not configured, or stdout suppressed
- **Check:** Capture stderr as well as stdout
- **Cure:** Use `2>&1` to capture both streams

---

## Evidence to Capture

- Exit code: Numeric exit code from container
- Error output: Full stderr/stdout from container
- Timing: How long until container exited
- Validation message: Specific Pydantic error text

---

## Notes

**Validation Flow:**
1. Worker module loads (`from ktrdr.config import validate_all`)
2. `warn_deprecated_env_vars()` runs (may emit warnings)
3. `validate_all("worker")` runs
4. Pydantic validates WorkerSettings
5. If validation fails, ConfigurationError is raised
6. Python exits with code 1

**Error Message Format:**
```
CONFIGURATION ERROR
====================
Invalid settings:
  - port: Input should be a valid integer, unable to parse string as an integer
====================
```

**Port Constraints in WorkerSettings:**
```python
port: int = deprecated_field(
    5003,
    "KTRDR_WORKER_PORT",
    "WORKER_PORT",
    ge=1,
    le=65535,
    description="Worker service port (canonical default: 5003)",
)
```
