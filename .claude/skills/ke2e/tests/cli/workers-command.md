# Test: cli/workers-command

**Purpose:** Validate `ktrdr workers` command displays worker status in table and JSON formats
**Duration:** ~30 seconds
**Category:** CLI / Workers

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox, API health
- [workers](../../preflight/workers.md) - Worker containers, registration

**Test-specific checks:**
- [ ] At least one worker registered with backend
- [ ] CLI entry point works: `uv run ktrdr --help`

---

## Test Data

```yaml
# No input data required - this is a read-only command
# Expected API response structure for reference:
expected_worker_fields:
  - worker_id
  - worker_type    # "backtesting", "training", "gpu_host"
  - endpoint_url
  - status         # "available", "busy", "temporarily_unavailable"
  - current_operation_id  # null or operation ID
  - capabilities   # dict with optional gpu_type, cores, memory_gb
```

**Why this data:** The test validates that CLI output matches API response structure.

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Run `ktrdr workers` | Table output with worker info | table_output |
| 2 | Run `ktrdr --json workers` | Valid JSON array | json_output |
| 3 | Query API directly | JSON response | api_response |
| 4 | Compare CLI JSON to API | Data matches | comparison_result |
| 5 | Verify exit codes | Both commands exit 0 | exit_codes |

---

### Step 1: Verify CLI Help Shows Workers Command

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

HELP_OUTPUT=$(uv run ktrdr --help 2>&1)
echo "$HELP_OUTPUT"

# Verify workers command exists
echo "$HELP_OUTPUT" | grep -q "workers" && echo "PASS: workers command found" || echo "FAIL: workers command not found"
```

**Expected:**
- Exit code 0
- Help text contains "workers" command

**Capture:** Help output showing workers command

---

### Step 2: Run Workers Command (Table Format)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

TABLE_OUTPUT=$(uv run ktrdr workers 2>&1)
EXIT_CODE=$?

echo "=== Table Output ==="
echo "$TABLE_OUTPUT"
echo "=== Exit Code: $EXIT_CODE ==="
```

**Expected:**
- Exit code 0
- Table output with headers (TYPE, STATUS, etc.)
- At least one worker row displayed
- Rich table formatting (borders, alignment)

**Capture:** Full table output, exit code

---

### Step 3: Run Workers Command (JSON Format)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

JSON_OUTPUT=$(uv run ktrdr --json workers 2>&1)
JSON_EXIT_CODE=$?

echo "=== JSON Output ==="
echo "$JSON_OUTPUT"
echo "=== Exit Code: $JSON_EXIT_CODE ==="
```

**Expected:**
- Exit code 0
- Output is valid JSON (parseable by jq)
- JSON is an array of worker objects

**Capture:** Full JSON output, exit code

---

### Step 4: Validate JSON is Parseable

**Command:**
```bash
# Parse JSON output
WORKER_COUNT=$(echo "$JSON_OUTPUT" | jq 'length')
FIRST_WORKER=$(echo "$JSON_OUTPUT" | jq '.[0]')

echo "Worker count: $WORKER_COUNT"
echo "First worker: $FIRST_WORKER"

# Verify required fields exist
echo "$JSON_OUTPUT" | jq -e '.[0].worker_id' > /dev/null && echo "PASS: worker_id field exists" || echo "FAIL: worker_id field missing"
echo "$JSON_OUTPUT" | jq -e '.[0].worker_type' > /dev/null && echo "PASS: worker_type field exists" || echo "FAIL: worker_type field missing"
echo "$JSON_OUTPUT" | jq -e '.[0].status' > /dev/null && echo "PASS: status field exists" || echo "FAIL: status field missing"
echo "$JSON_OUTPUT" | jq -e '.[0].endpoint_url' > /dev/null && echo "PASS: endpoint_url field exists" || echo "FAIL: endpoint_url field missing"
```

**Expected:**
- jq parses successfully (exit 0)
- Worker count >= 1
- All required fields present: worker_id, worker_type, status, endpoint_url

**Capture:** Parsed field values, worker count

---

### Step 5: Compare CLI JSON to API Response

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Get API response
API_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/workers")
echo "=== API Response ==="
echo "$API_RESPONSE" | jq '.'

# Compare worker counts
API_WORKER_COUNT=$(echo "$API_RESPONSE" | jq 'length')
CLI_WORKER_COUNT=$(echo "$JSON_OUTPUT" | jq 'length')

echo "API worker count: $API_WORKER_COUNT"
echo "CLI worker count: $CLI_WORKER_COUNT"

if [ "$API_WORKER_COUNT" = "$CLI_WORKER_COUNT" ]; then
  echo "PASS: Worker counts match"
else
  echo "FAIL: Worker counts differ (API=$API_WORKER_COUNT, CLI=$CLI_WORKER_COUNT)"
fi

# Compare first worker's key fields
API_FIRST_ID=$(echo "$API_RESPONSE" | jq -r '.[0].worker_id')
CLI_FIRST_ID=$(echo "$JSON_OUTPUT" | jq -r '.[0].worker_id')

API_FIRST_TYPE=$(echo "$API_RESPONSE" | jq -r '.[0].worker_type')
CLI_FIRST_TYPE=$(echo "$JSON_OUTPUT" | jq -r '.[0].worker_type')

echo "API first worker: id=$API_FIRST_ID, type=$API_FIRST_TYPE"
echo "CLI first worker: id=$CLI_FIRST_ID, type=$CLI_FIRST_TYPE"

# Note: Order may differ, so just verify all IDs exist in both
for worker_id in $(echo "$API_RESPONSE" | jq -r '.[].worker_id'); do
  if echo "$JSON_OUTPUT" | jq -e --arg id "$worker_id" '.[] | select(.worker_id == $id)' > /dev/null 2>&1; then
    echo "PASS: Worker $worker_id found in CLI output"
  else
    echo "FAIL: Worker $worker_id missing from CLI output"
  fi
done
```

**Expected:**
- Worker counts match between API and CLI
- All worker IDs from API are present in CLI output
- Worker types match between API and CLI

**Capture:** API response, comparison results

---

### Step 6: Verify Table Has Expected Columns

**Command:**
```bash
# Check for expected column headers in table output
# Expected columns: TYPE, STATUS, GPU, ENDPOINT, OPERATION

echo "$TABLE_OUTPUT" | grep -q "TYPE" && echo "PASS: TYPE column found" || echo "WARN: TYPE column not found"
echo "$TABLE_OUTPUT" | grep -q "STATUS" && echo "PASS: STATUS column found" || echo "WARN: STATUS column not found"
echo "$TABLE_OUTPUT" | grep -q "ENDPOINT" && echo "PASS: ENDPOINT column found" || echo "WARN: ENDPOINT column not found"

# Check for worker type values (backtesting or training)
echo "$TABLE_OUTPUT" | grep -qE "(backtesting|training)" && echo "PASS: Worker type values present" || echo "FAIL: No worker type values found"

# Check for status values (available or busy)
echo "$TABLE_OUTPUT" | grep -qE "(available|busy)" && echo "PASS: Status values present" || echo "WARN: Status values not found in expected format"
```

**Expected:**
- Table contains TYPE, STATUS, ENDPOINT headers
- Worker type values visible (backtesting, training)
- Status values visible (available, busy)

**Capture:** Column verification results

---

## Success Criteria

All must pass for test to pass:

- [ ] `ktrdr --help` shows workers command
- [ ] `ktrdr workers` exits with code 0
- [ ] `ktrdr workers` displays formatted table output
- [ ] `ktrdr --json workers` exits with code 0
- [ ] `ktrdr --json workers` outputs valid JSON array
- [ ] JSON output contains required fields (worker_id, worker_type, status, endpoint_url)
- [ ] CLI JSON worker count matches API worker count
- [ ] All API workers are represented in CLI output

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Worker count > 0 | 0 workers fails | Workers not registered or CLI not calling API |
| JSON is array | Non-array fails | Wrong output format or error message instead |
| Table has rows | Header-only fails | CLI rendering issue or empty response handling |
| Fields match spec | Missing fields fails | API or CLI schema mismatch |
| Exit code = 0 | Non-zero fails | Command error or exception |

**Verification command:**
```bash
# Quick sanity check
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

API_COUNT=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq 'length')
CLI_COUNT=$(uv run ktrdr --json workers 2>&1 | jq 'length')

echo "API workers: $API_COUNT, CLI workers: $CLI_COUNT"
[ "$API_COUNT" -gt 0 ] && [ "$API_COUNT" = "$CLI_COUNT" ] && echo "SANITY OK" || echo "SANITY FAIL"
```

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Command not found | CODE_BUG | Check workers.py exists and is registered in app.py |
| Non-zero exit code | CODE_BUG | Check error handling in workers command |
| Invalid JSON output | CODE_BUG | Check json_mode handling in workers command |
| Empty output | ENVIRONMENT | Verify workers are registered (preflight/workers.md) |
| Field mismatch | CODE_BUG | Check CLI is passing through API response correctly |
| Table formatting broken | CODE_BUG | Check Rich table construction in workers command |
| Connection refused | ENVIRONMENT | Docker not running or wrong port |

---

## Cleanup

None required - this is a read-only command.

---

## Troubleshooting

**If "workers" command not found:**
- **Cause:** Command not registered in app.py
- **Check:** `grep -r "workers" ktrdr/cli/app.py`
- **Cure:** Add `app.add_command(workers)` to app.py

**If JSON output contains error message:**
- **Cause:** API error or connection issue
- **Check:** Error message in output, verify API is responsive
- **Cure:** Check API health, verify port configuration

**If worker count is 0:**
- **Cause:** Workers not registered
- **Check:** `curl localhost:$API_PORT/api/v1/workers`
- **Cure:** Run preflight/workers.md checks, restart worker containers

**If table has no data rows:**
- **Cause:** Empty response handling or rendering issue
- **Check:** JSON output for comparison
- **Cure:** Check table construction handles worker list correctly

**If fields missing from JSON:**
- **Cause:** CLI filtering or transforming API response
- **Check:** Compare raw API response to CLI output
- **Cure:** CLI should pass through API response unchanged in JSON mode

---

## Evidence to Capture

- Command help output showing workers command
- Table format output
- JSON format output
- API response for comparison
- Exit codes from both commands
- Field-by-field comparison results

---

## Notes for Implementation

- **Sandbox awareness:** Always source `.env.sandbox` before commands to get correct API port
- **JSON mode flag:** Use `ktrdr --json workers` (global flag before command)
- **API endpoint:** `/api/v1/workers` returns flat array, not wrapped in `{workers: [...]}`
- **Worker types:** Expect "backtesting" and "training" (not "backtest" or "train")
- **Status values:** "available", "busy", or "temporarily_unavailable"
- **Timing:** Run API query close to CLI query to avoid registration state changes
