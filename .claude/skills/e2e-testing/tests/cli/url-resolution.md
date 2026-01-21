# Test: cli/url-resolution

**Purpose:** Validate CLI URL resolution priority: --url > --port > .env.sandbox > default
**Duration:** ~15 seconds
**Category:** CLI / Infrastructure

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox, API health

**Test-specific checks:**
- [ ] `.env.sandbox` file exists with `KTRDR_API_PORT` set
- [ ] Backend is running on the sandbox port
- [ ] No other KTRDR backends running on default port 8000 (to avoid false positives)

---

## Test Data

```yaml
sandbox_port: 8002   # From .env.sandbox
wrong_port: 8099     # Non-existent backend for negative test
explicit_port: 8002  # For --port flag test
```

**Why this data:**
- Uses actual sandbox port to verify auto-detection
- Uses non-existent port to verify error behavior
- Tests the priority chain documented in sandbox_detect.py

---

## Execution Steps

### 1. Verify Test Preconditions

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Check .env.sandbox exists and has port
if [ ! -f .env.sandbox ]; then
  echo "FAIL: .env.sandbox not found - not in a sandbox environment"
  exit 1
fi

SANDBOX_PORT=$(grep KTRDR_API_PORT .env.sandbox | cut -d= -f2)
echo "Sandbox port from file: $SANDBOX_PORT"

# Verify backend is running on sandbox port
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$SANDBOX_PORT/api/v1/health)
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Backend not responding on sandbox port $SANDBOX_PORT (HTTP $HTTP_CODE)"
  exit 1
fi
echo "OK: Backend healthy on port $SANDBOX_PORT"
```

**Expected:**
- .env.sandbox exists
- KTRDR_API_PORT is set (e.g., 8002)
- Backend responds 200 on that port

### 2. Test Sandbox Auto-Detection (No Flags)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run ops without any URL/port flags - should auto-detect from .env.sandbox
uv run ktrdr ops --limit 1 2>&1
EXIT_CODE=$?

echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code 0
- Table output or "No operations found" (both prove connectivity)
- No connection errors

**Evidence to Capture:**
- Command output
- Exit code

### 3. Test --port Flag Override

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Get sandbox port
SANDBOX_PORT=$(grep KTRDR_API_PORT .env.sandbox | cut -d= -f2)

# Explicitly specify --port (should work, same as auto-detected)
uv run ktrdr --port $SANDBOX_PORT ops --limit 1 2>&1
EXIT_CODE=$?

echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code 0
- Same behavior as auto-detection (connectivity confirmed)

### 4. Test --url Flag Override

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Get sandbox port
SANDBOX_PORT=$(grep KTRDR_API_PORT .env.sandbox | cut -d= -f2)

# Explicitly specify --url (should work)
uv run ktrdr --url "http://localhost:$SANDBOX_PORT" ops --limit 1 2>&1
EXIT_CODE=$?

echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code 0
- Connectivity confirmed via --url override

### 5. Test --port Flag with Wrong Port (Negative Test)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Use wrong port - should fail with connection error
uv run ktrdr --port 8099 ops --limit 1 2>&1
EXIT_CODE=$?

echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code 1 (failure)
- Error message containing "connection" or "refused" or similar
- This proves --port flag actually overrides sandbox detection

**Evidence to Capture:**
- Error message
- Exit code (must be non-zero)

### 6. Test --url Flag with Wrong URL (Negative Test)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Use wrong URL - should fail with connection error
uv run ktrdr --url "http://localhost:8099" ops --limit 1 2>&1
EXIT_CODE=$?

echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code 1 (failure)
- Error message about connection failure
- This proves --url flag actually overrides sandbox detection

### 7. Verify Priority Chain: --url > --port

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Get sandbox port
SANDBOX_PORT=$(grep KTRDR_API_PORT .env.sandbox | cut -d= -f2)

# Specify BOTH --url (correct) and --port (wrong)
# --url should win per documented priority
uv run ktrdr --url "http://localhost:$SANDBOX_PORT" --port 8099 ops --limit 1 2>&1
EXIT_CODE=$?

echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code 0 (success)
- --url takes priority over --port
- Connectivity confirmed (proves --url won)

---

## Success Criteria

- [ ] **Sandbox auto-detection works** - `ktrdr ops` (no flags) connects to sandbox backend
- [ ] **--port flag works** - Explicit port connects successfully
- [ ] **--url flag works** - Explicit URL connects successfully
- [ ] **--port override verified** - Wrong port causes connection failure (not sandbox fallback)
- [ ] **--url override verified** - Wrong URL causes connection failure (not sandbox fallback)
- [ ] **Priority verified** - --url beats --port when both specified

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Auto-detect exit code = 0 | != 0 fails | Sandbox detection broken |
| Wrong port exit code != 0 | = 0 fails | Override not working (fell back to sandbox) |
| Wrong URL exit code != 0 | = 0 fails | Override not working (fell back to sandbox) |
| Priority test exit code = 0 | != 0 fails | Priority chain broken |

**Key Insight:** The negative tests (wrong port/URL) are the most important sanity checks. If they succeed, the CLI is ignoring the flags and falling back to sandbox detection, which defeats the purpose of the override flags.

---

## Troubleshooting

**If auto-detection fails (Step 2):**
- **Cause:** .env.sandbox not being read or parsed correctly
- **Cure:** Check file format, verify `KTRDR_API_PORT=XXXX` line exists

**If wrong port succeeds (Step 5):**
- **Cause:** --port flag not being applied, sandbox fallback taking over
- **Cure:** Check resolve_api_url() priority logic in sandbox_detect.py

**If wrong URL succeeds (Step 6):**
- **Cause:** --url flag not being applied
- **Cure:** Check normalize_api_url() and set_url_override() in sandbox_detect.py

**If priority test fails (Step 7):**
- **Cause:** --port taking priority over --url
- **Cure:** Check resolve_api_url() priority order - should be url > port > sandbox > default

**If all tests fail with connection errors:**
- **Cause:** Docker not running or backend container down
- **Cure:** Run `uv run ktrdr sandbox status` and `docker compose -f docker-compose.sandbox.yml up -d`

---

## Cleanup

None required - test is read-only, no state modified.

---

## Evidence to Capture

For each step:
- Command output (stdout/stderr)
- Exit code
- Actual port being targeted (from verbose output if available)

**Summary evidence:**
```json
{
  "sandbox_port": "XXXX",
  "auto_detect": {"exit_code": 0, "success": true},
  "port_flag": {"exit_code": 0, "success": true},
  "url_flag": {"exit_code": 0, "success": true},
  "wrong_port": {"exit_code": 1, "success": false, "error": "..."},
  "wrong_url": {"exit_code": 1, "success": false, "error": "..."},
  "priority": {"exit_code": 0, "success": true}
}
```

---

## Implementation Notes

### Why `ktrdr ops` for Testing

- **Fast:** Single API call to list operations
- **Non-destructive:** Read-only, no side effects
- **Reliable indicator:** Any response (even empty list) proves connectivity
- **Clear failure mode:** Connection errors are unambiguous

### Priority Chain Reference

From `ktrdr/cli/sandbox_detect.py`:
```
Priority order (highest to lowest):
1. explicit_url: Explicit --url flag, always wins
2. explicit_port: --port flag, convenience for localhost
3. .env.sandbox file: Auto-detect from current directory tree
4. Default: http://localhost:8000
```

### Working Directory Matters

The sandbox detection walks UP the directory tree to find `.env.sandbox`. Tests must run from within the project directory (or a subdirectory) for auto-detection to work.

### JSON Output Alternative

If table output is hard to parse, use `ktrdr --json ops` for machine-readable output:
```bash
uv run ktrdr --json ops --limit 1 2>&1 | jq -e '.' && echo "Valid JSON" || echo "Not JSON or error"
```
