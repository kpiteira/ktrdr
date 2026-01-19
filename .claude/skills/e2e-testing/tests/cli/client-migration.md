# Test: cli/client-migration

**Purpose:** Validate all CLI commands work before and after deleting old client files, proving the migration to the unified client is complete
**Duration:** ~2 minutes
**Category:** CLI / Migration

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Docker containers are running
- [ ] API responds on health endpoint
- [ ] KTRDR CLI is available: `uv run ktrdr --help` succeeds
- [ ] Test data exists: EURUSD 1d has cached data
- [ ] Strategy file exists: `strategies/v3_minimal.yaml`

---

## Test Data

```yaml
symbol: EURUSD
timeframe: 1d
start_date: "2024-01-01"
end_date: "2024-01-31"
strategy_file: v3_minimal.yaml
test_operation_id: test_op_123  # Fake ID for checkpoint show (will 404, that's expected)
```

**Why this data:**
- EURUSD 1d: Standard test symbol with cached data
- v3_minimal: Known-good strategy for testing
- test_op_123: Intentionally non-existent to verify error handling works (no import errors on 404)

---

## Execution Steps

### Phase 1: Pre-Deletion Validation

#### 1.1 CLI Help

**Command:**
```bash
uv run ktrdr --help 2>&1
echo "Exit code: $?"
```

**Expected:**
- Exit code = 0
- Output shows command groups (data, indicators, strategies, operations, etc.)
- No Python tracebacks

#### 1.2 Sync Commands

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Test data show
uv run ktrdr data show EURUSD --timeframe 1d 2>&1 | head -50
echo "data show exit: $?"

# Test indicators list
uv run ktrdr indicators list 2>&1 | head -30
echo "indicators list exit: $?"

# Test strategies list
uv run ktrdr list strategies 2>&1 | head -30
echo "list strategies exit: $?"

# Test operations list
uv run ktrdr ops 2>&1 | head -30
echo "ops exit: $?"

# Test ib status
uv run ktrdr ib status 2>&1 | head -30
echo "ib status exit: $?"
```

**Expected:**
- All commands execute (exit 0 or reasonable error codes)
- No `ImportError`, `ModuleNotFoundError`, or `AttributeError` in stderr

#### 1.3 Async Commands

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Test research status (replaces agent status)
uv run ktrdr status 2>&1 | head -20
echo "status exit: $?"

# Test checkpoints show (will 404 but should not have import errors)
uv run ktrdr checkpoints show test_op_123 2>&1 | head -20
echo "checkpoints show exit: $?"
```

**Expected:**
- status: Exits 0, shows operations or "No operations"
- checkpoints show: May exit non-zero (404 expected), but no import errors

#### 1.4 Operation Commands (Dry Run)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Test train help
uv run ktrdr train --help 2>&1 | head -20
echo "train help exit: $?"

# Test backtest help
uv run ktrdr backtest --help 2>&1 | head -20
echo "backtest help exit: $?"
```

**Expected:**
- Help commands exit 0
- No import errors

### Phase 2: Import Verification

#### 2.1 Test Client Imports

**Command:**
```bash
uv run python -c "
from ktrdr.cli.client import (
    AsyncCLIClient,
    SyncCLIClient,
    CLIClientError,
)
print('All client imports successful')
" 2>&1
echo "Client import test exit: $?"
```

**Expected:**
- Exit code = 0
- Prints "All client imports successful"

#### 2.2 Test Command Module Imports

**Command:**
```bash
uv run python -c "
from ktrdr.cli import data_commands
from ktrdr.cli import indicator_commands
from ktrdr.cli import strategy_commands
from ktrdr.cli import operations_commands
from ktrdr.cli import agent_commands
from ktrdr.cli import backtest_commands
from ktrdr.cli import checkpoints_commands
from ktrdr.cli import ib_commands
print('All command module imports successful')
" 2>&1
echo "Command modules import test exit: $?"
```

**Expected:**
- Exit code = 0
- Prints "All command module imports successful"

### Phase 3: Post-Deletion Verification

**Note:** After deleting old client files, repeat Phase 1 and Phase 2.

#### 3.1 Identify Old Client Files

**Command:**
```bash
# Check for remaining old imports
grep -r "from ktrdr.cli.api_client" ktrdr/cli/*.py 2>/dev/null || echo "No old api_client imports found"
grep -r "from ktrdr.cli.async_cli_client" ktrdr/cli/*.py 2>/dev/null || echo "No old async_cli_client imports found"
grep -r "from ktrdr.cli.operation_executor" ktrdr/cli/*.py 2>/dev/null || echo "No old operation_executor imports found"
```

**Expected:**
- All greps return "No old ... imports found"

---

## Success Criteria

- [ ] `ktrdr --help` exits 0 with no Python errors
- [ ] All sync commands execute without ImportError
- [ ] All async commands execute without ImportError
- [ ] Operation commands work in help mode
- [ ] Direct Python imports of `ktrdr.cli.client` succeed
- [ ] All command module imports succeed
- [ ] No command output contains "ImportError", "ModuleNotFoundError", or "AttributeError"
- [ ] After deletion: all criteria still pass

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Commands produce output** — Empty output = command not executing
- [ ] **Exit codes are 0 or expected** — Unexpected exit code = crashing
- [ ] **stderr has no Python tracebacks** — Traceback = import or runtime error
- [ ] **At least 8 commands tested** — Fewer = test not comprehensive

---

## Troubleshooting

**If ImportError appears:**
- **Cause:** Migration incomplete - old import still in command file
- **Cure:** Check the file mentioned in error, update import to `ktrdr.cli.client`

**If ModuleNotFoundError for old client:**
- **Cause:** Command still imports deleted file
- **Cure:** Find the import with `grep -r "from ktrdr.cli.api_client" ktrdr/`

**If commands hang > 30s:**
- **Cause:** Docker/API connectivity issue
- **Cure:** Check `docker compose ps`, restart if needed

---

## Evidence to Capture

- Full stdout/stderr of each command
- Exit codes
- Grep results for import errors
- Timestamp of test execution
