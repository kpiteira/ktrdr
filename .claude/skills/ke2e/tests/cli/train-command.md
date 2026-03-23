# Test: cli/train-command

**Purpose:** Validate new CLI restructure works end-to-end: entry point, train command, fire-and-follow pattern, JSON output
**Duration:** ~60 seconds
**Category:** CLI / Restructure

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [training](../../preflight/training.md) — Strategy, data, workers

**Test-specific checks:**
- [ ] New entry point exists: `python -m ktrdr.cli.app --help` works
- [ ] Strategy available: `test_e2e_local_pull`
- [ ] EURUSD 1d data cached

---

## Test Data

```json
{
  "strategy": "test_e2e_local_pull",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31"
}
```

**Why this data:**
- test_e2e_local_pull: Known-good strategy for E2E tests
- 5-year range: ~1300 samples, trains in ~3s (fast but not instant)

---

## Execution Steps

### 1. Display Help via New Entry Point

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

HELP_OUTPUT=$(uv run python -m ktrdr.cli.app --help 2>&1)
echo "$HELP_OUTPUT"
```

**Expected:**
- Exit code 0
- Output contains `train` command
- Output contains `--json` global flag
- Output contains `--verbose` or `-v` flag

### 2. Start Training Fire-and-Forget

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

START_TIME=$(date +%s.%N)

RESPONSE=$(uv run python -m ktrdr.cli.app train test_e2e_local_pull \
  --start 2020-01-01 \
  --end 2024-12-31 \
  2>&1)

END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

echo "Response: $RESPONSE"
echo "Duration: ${DURATION}s"

OPERATION_ID=$(echo "$RESPONSE" | grep -oE 'op_[a-zA-Z0-9_]+' | head -1)
echo "Operation ID: $OPERATION_ID"
```

**Expected:**
- Exit code 0
- Response contains "Started training:" or similar
- Response contains operation ID (op_xxx format)
- Duration < 2 seconds (returns immediately)
- Response includes follow-up hints

### 3. Verify Operation in Backend API

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

sleep 1
API_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")

echo "API Response: $API_RESPONSE"

OP_TYPE=$(echo "$API_RESPONSE" | jq -r '.data.operation_type // .type // "unknown"')
OP_STATUS=$(echo "$API_RESPONSE" | jq -r '.data.status // .status // "unknown"')

echo "Type: $OP_TYPE, Status: $OP_STATUS"
```

**Expected:**
- HTTP 200 (operation exists)
- Operation type is "training"
- Status is "running" or "pending" or "completed"

### 4. Test JSON Output Mode

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

JSON_RESPONSE=$(uv run python -m ktrdr.cli.app --json train test_e2e_local_pull \
  --start 2020-01-01 \
  --end 2024-12-31 \
  2>&1)

echo "JSON Response: $JSON_RESPONSE"
```

**Expected:**
- Exit code 0
- Output is valid JSON
- JSON contains `operation_id` field
- JSON contains `status` field ("started")
- JSON contains `type` field ("training")

### 5. Verify JSON Parseable

**Command:**
```bash
EXTRACTED_ID=$(echo "$JSON_RESPONSE" | jq -r '.operation_id')
EXTRACTED_STATUS=$(echo "$JSON_RESPONSE" | jq -r '.status')
EXTRACTED_TYPE=$(echo "$JSON_RESPONSE" | jq -r '.type')

echo "Extracted - ID: $EXTRACTED_ID, Status: $EXTRACTED_STATUS, Type: $EXTRACTED_TYPE"

[ "$EXTRACTED_ID" != "null" ] && [ -n "$EXTRACTED_ID" ] && echo "OK: operation_id present"
[ "$EXTRACTED_STATUS" = "started" ] && echo "OK: status is started"
[ "$EXTRACTED_TYPE" = "training" ] && echo "OK: type is training"
```

**Expected:**
- jq exits successfully
- `operation_id` not null
- `status` equals "started"
- `type` equals "training"

### 6. Start Training with --follow

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

START_TIME=$(date +%s)

FOLLOW_OUTPUT=$(timeout 120 uv run python -m ktrdr.cli.app train test_e2e_local_pull \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --follow \
  2>&1)

EXIT_CODE=$?
END_TIME=$(date +%s)
FOLLOW_DURATION=$((END_TIME - START_TIME))

echo "Follow Output: $FOLLOW_OUTPUT"
echo "Exit Code: $EXIT_CODE"
echo "Duration: ${FOLLOW_DURATION}s"
```

**Expected:**
- Exit code 0 (not timeout 124)
- Output shows progress (epoch, percentage)
- Output indicates completion
- Duration > 3 seconds (actually ran)
- Duration < 120 seconds

---

## Success Criteria

- [ ] Help text includes `train` command
- [ ] Help text includes `--json` global flag
- [ ] Fire-and-forget returns operation ID
- [ ] Fire-and-forget completes in < 2 seconds
- [ ] Operation visible in backend API
- [ ] Operation type is "training"
- [ ] JSON mode produces valid JSON
- [ ] JSON contains operation_id, status, type fields
- [ ] JSON parseable by jq
- [ ] Follow mode shows progress and completes
- [ ] Follow mode duration > 3 seconds (not instant)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Fire-and-forget duration <= 2s** — CLI blocking = bug
- [ ] **Follow duration > 3s** — Training skipped = bug
- [ ] **Follow duration < 120s** — Training hung = environment issue
- [ ] **Operation exists in API** — CLI didn't create operation = bug
- [ ] **JSON has all fields** — Incomplete output = bug
- [ ] **Help shows train** — Command not registered = bug

**Check command:**
```bash
OP_COUNT=$(curl -s "http://localhost:$API_PORT/api/v1/operations" | jq '[.data[] | select(.operation_type == "training")] | length')
echo "Training operations: $OP_COUNT"
[ "$OP_COUNT" -ge 2 ] && echo "OK" || echo "FAIL: Expected >= 2"
```

---

## Troubleshooting

**If ModuleNotFoundError: ktrdr.cli.app:**
- **Cause:** Entry point not created
- **Cure:** Check `ktrdr/cli/app.py` exists

**If help missing train command:**
- **Cause:** Command not registered
- **Cure:** Check `app.py` command registration

**If fire-and-forget takes > 5s:**
- **Cause:** Operation runner following when it shouldn't
- **Cure:** Check follow flag handling in operation_runner.py

**If JSON not parseable:**
- **Cause:** Formatting error in output.py
- **Cure:** Check print_operation_started JSON path

---

## Evidence to Capture

- Help output
- Fire-and-forget response and duration
- Operation ID
- API response
- JSON response
- Follow output and duration
