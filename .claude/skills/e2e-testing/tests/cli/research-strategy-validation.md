# E2E Test: cli/research-strategy-validation

**Purpose:** Validate CLI `--strategy` flag acceptance, mutual exclusivity with goal argument, and proper error handling for invalid strategies

**Duration:** ~30 seconds

**Category:** CLI / Validation

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox, API health

**Test-specific checks:**
- [ ] CLI entry point works: `uv run python -m ktrdr.cli.app --help` exits 0
- [ ] v3_minimal strategy exists in strategies/ directory

---

## Test Data

```json
{
  "valid_strategy": "v3_minimal",
  "nonexistent_strategy": "nonexistent_strategy_xyz_12345",
  "test_goal": "build a simple momentum strategy"
}
```

**Why this data:**
- v3_minimal: Known valid v3 strategy, minimal and fast
- nonexistent_strategy: Deliberately invalid name to test error handling
- test_goal: Simple goal string to test mutual exclusivity

---

## Execution Steps

### 1. Verify Help Shows --strategy Option

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

HELP_OUTPUT=$(uv run python -m ktrdr.cli.app research --help 2>&1)
echo "$HELP_OUTPUT"

# Check for --strategy option
echo "$HELP_OUTPUT" | grep -q -- '--strategy' && echo "OK: --strategy in help" || echo "FAIL: --strategy not in help"
echo "$HELP_OUTPUT" | grep -q -- '-s' && echo "OK: -s shorthand in help" || echo "FAIL: -s not in help"
```

**Expected:**
- Exit code 0
- Output contains `--strategy` option
- Output contains `-s` shorthand
- Help mentions "existing v3 strategy" or similar

### 2. Test --strategy Flag Acceptance (Fire-and-Forget)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Use --strategy with valid strategy name (will trigger, then we'll cancel)
RESPONSE=$(uv run python -m ktrdr.cli.app research --strategy v3_minimal 2>&1)
EXIT_CODE=$?

echo "Response: $RESPONSE"
echo "Exit code: $EXIT_CODE"

# Extract operation ID for cleanup
OPERATION_ID=$(echo "$RESPONSE" | grep -oE 'op_[a-zA-Z0-9_]+' | head -1)
echo "Operation ID: $OPERATION_ID"

# Cancel the operation to avoid consuming resources
if [ -n "$OPERATION_ID" ]; then
  curl -s -X DELETE "http://localhost:$API_PORT/api/v1/agent/cancel/$OPERATION_ID" | jq
fi
```

**Expected:**
- Exit code 0
- Response contains operation ID (op_xxx format)
- Response indicates "Started research" or similar

### 3. Test -s Shorthand Flag

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Use -s shorthand
RESPONSE=$(uv run python -m ktrdr.cli.app research -s v3_minimal 2>&1)
EXIT_CODE=$?

echo "Response: $RESPONSE"
echo "Exit code: $EXIT_CODE"

OPERATION_ID=$(echo "$RESPONSE" | grep -oE 'op_[a-zA-Z0-9_]+' | head -1)
echo "Operation ID: $OPERATION_ID"

# Cancel for cleanup
if [ -n "$OPERATION_ID" ]; then
  curl -s -X DELETE "http://localhost:$API_PORT/api/v1/agent/cancel/$OPERATION_ID" | jq
fi
```

**Expected:**
- Exit code 0
- Response contains operation ID
- Shorthand `-s` works identically to `--strategy`

### 4. Test Mutual Exclusivity: Reject Both Goal and --strategy

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Attempt to provide both goal AND --strategy
RESPONSE=$(uv run python -m ktrdr.cli.app research "build momentum strategy" --strategy v3_minimal 2>&1)
EXIT_CODE=$?

echo "Response: $RESPONSE"
echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code != 0 (should fail)
- Error message mentions "cannot" or "both" or "mutually exclusive"
- No operation ID created

### 5. Test Missing Both Goal and --strategy

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Attempt to invoke without goal OR --strategy
RESPONSE=$(uv run python -m ktrdr.cli.app research 2>&1)
EXIT_CODE=$?

echo "Response: $RESPONSE"
echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code != 0 (should fail)
- Error message mentions "either" or "required" or "goal"

### 6. Test Non-Existent Strategy Error

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Use a strategy name that doesn't exist
RESPONSE=$(uv run python -m ktrdr.cli.app research --strategy nonexistent_strategy_xyz_12345 2>&1)
EXIT_CODE=$?

echo "Response: $RESPONSE"
echo "Exit code: $EXIT_CODE"
```

**Expected:**
- Exit code != 0 (should fail)
- Error message contains "not found" or "Strategy not found"
- Error message is user-friendly (not a stack trace)

### 7. Test API Returns 422 for Invalid Strategy

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Call API directly with invalid strategy
RESPONSE=$(curl -s -i -X POST "http://localhost:$API_PORT/api/v1/agent/trigger" \
  -H "Content-Type: application/json" \
  -d '{"strategy": "nonexistent_strategy_xyz_12345"}')

echo "$RESPONSE"

# Extract HTTP status code
HTTP_CODE=$(echo "$RESPONSE" | grep -E "^HTTP" | head -1 | awk '{print $2}')
echo "HTTP Code: $HTTP_CODE"
```

**Expected:**
- HTTP 422 (Unprocessable Entity)
- Response body contains error detail about strategy not found
- Not HTTP 500 (should be client error, not server error)

---

## Success Criteria

- [ ] Help text shows `--strategy` option
- [ ] Help text shows `-s` shorthand
- [ ] `--strategy v3_minimal` triggers research successfully
- [ ] `-s v3_minimal` triggers research successfully
- [ ] Both goal and `--strategy` together is rejected
- [ ] Neither goal nor `--strategy` is rejected
- [ ] Non-existent strategy returns clear error
- [ ] API returns HTTP 422 for invalid strategy (not 500)
- [ ] Error messages are user-friendly (no stack traces)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Exit code 0 only when expected** - Success cases should exit 0, error cases should exit non-zero
- [ ] **Operation IDs are real** - op_xxx format present in success responses
- [ ] **HTTP 422 not 500** - Strategy validation is client error, not server crash
- [ ] **No stack traces in CLI output** - Errors are user-friendly

---

## Troubleshooting

**If help missing --strategy:**
- **Cause:** CLI option not registered
- **Cure:** Check `ktrdr/cli/commands/research.py` for strategy Option definition

**If mutual exclusivity not enforced:**
- **Cause:** Validation logic missing in research command
- **Cure:** Check research() function for goal/strategy validation

**If HTTP 500 for invalid strategy:**
- **Cause:** Unhandled exception in API
- **Cure:** Check agent_service._validate_and_resolve_strategy() for proper error handling

**If stack trace in CLI output:**
- **Cause:** Exception not caught in CLI layer
- **Cure:** Check research() try/except block and print_error() usage

---

## Evidence to Capture

- Help output showing --strategy option
- Operation IDs from successful triggers
- Error messages from validation failures
- HTTP response codes from API calls
