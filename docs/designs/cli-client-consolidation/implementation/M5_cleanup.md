---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Cleanup

**Branch:** `feature/cli-client-consolidation-m5`
**Builds on:** M2, M3, M4, M4.5
**Goal:** Old client code deleted. Single source of truth.

## E2E Test Scenario

**E2E Test Recipe:** [cli/client-migration](../../../../.claude/skills/e2e-testing/tests/cli/client-migration.md)

```bash
# Verify no references to old clients
grep -r "from ktrdr.cli.async_cli_client" ktrdr/
grep -r "from ktrdr.cli.api_client" ktrdr/
grep -r "from ktrdr.cli.operation_executor" ktrdr/

# Should return nothing

# Verify all tests pass
make test-unit
make quality

# FULL E2E: Run all commands and verify SUCCESS (see Task 5.0 and 5.4)
# This requires IB host service + Anthropic API key
# Commands must complete successfully, not just start
```

**Success Criteria:**
- [ ] **Pre-deletion E2E verification passed (Task 5.0)**
- [ ] Old files deleted
- [ ] No references remain
- [ ] All tests pass
- [ ] **Post-deletion verification passed (Task 5.4)**

---

## Task 5.0: Pre-Deletion E2E Verification

**Type:** TESTING
**Task Categories:** E2E

**Description:**
Before deleting any old client files, verify ALL API-based CLI commands work correctly with the new unified client. This establishes a baseline — if anything fails here, fix it before proceeding with deletion.

**Prerequisites (ask user to ensure before starting):**
- IB host service running and connected
- Docker environment running (`docker compose up`)
- Market data available for test symbols
- Anthropic API key configured (for agent commands)

**Commands to test (must ALL succeed):**

```bash
# =============================================================================
# SYNC COMMANDS (use SyncCLIClient)
# =============================================================================

# --- Data commands ---
ktrdr data show AAPL --start 2024-01-01           # Display cached data
ktrdr data range AAPL                              # Get available date range
ktrdr data load AAPL --timeframe 1h --start 2024-01-01 --end 2024-03-31  # Load via API (requires IB)

# --- Indicator commands ---
ktrdr indicators list                              # List available indicators
ktrdr indicators compute AAPL 1d RSI               # Compute indicator (optional)

# --- Strategy commands ---
ktrdr strategies list                              # List strategies
ktrdr strategies validate strategies/v3_minimal.yaml  # Validate strategy

# --- Operations commands ---
ktrdr operations list                              # List operations

# --- Fuzzy commands ---
ktrdr fuzzy config validate --config config/fuzzy.yaml  # Validate config

# --- IB commands (requires IB host service) ---
ktrdr ib status                                    # Check IB connection status
ktrdr ib test                                      # Test IB connection

# =============================================================================
# ASYNC COMMANDS (use AsyncCLIClient)
# =============================================================================

# --- Checkpoint commands ---
ktrdr checkpoints show test_op_123                 # Show checkpoint (expect 404 for non-existent)

# --- Agent commands (requires Anthropic API key) ---
ktrdr agent status                                 # Show agent status
ktrdr agent budget                                 # Show budget status

# =============================================================================
# OPERATION COMMANDS (use AsyncCLIClient.execute_operation)
# =============================================================================

# --- Training (wait for completion) ---
ktrdr models train strategies/v3_minimal.yaml --start-date 2024-01-01 --end-date 2024-03-31

# --- Backtest (wait for completion) ---
ktrdr backtest run v3_minimal EURUSD 1h --start-date 2024-01-01 --end-date 2024-03-31

# --- Dummy (for testing operation pattern) ---
ktrdr dummy dummy
```

**Process:**
1. Ask user: "Please ensure Docker is running, IB host service is available, and Anthropic API key is set"
2. Run each command and verify success
3. For long-running operations (training, backtest), wait for actual completion
4. Commands may fail at infrastructure layer (IB not connected, no API key) — that's OK
5. Commands must NOT fail at client layer (connection, HTTP, parsing)
6. Document all results

**Acceptance Criteria:**
- [ ] All data commands succeed (show, range, load*)
- [ ] All indicator commands succeed (list, compute)
- [ ] All strategy commands succeed (list, validate)
- [ ] All operations commands succeed (list)
- [ ] All fuzzy commands succeed (config validate)
- [ ] All IB commands succeed (status, test*)
- [ ] All checkpoint commands succeed (show)
- [ ] All agent commands succeed (status, budget*)
- [ ] Training completes successfully (not just starts)
- [ ] Backtest completes successfully (not just starts)
- [ ] Dummy operation completes successfully
- [ ] No commands fail due to client issues
- [ ] Results documented

*Commands marked with asterisk may fail at infrastructure layer (IB, Anthropic) — that's acceptable if the client layer works.

**If any test fails due to client issues:** Stop. Do not proceed to Task 5.1. Fix the issue first.

---

## Task 5.1: Delete async_cli_client.py

**File(s):** `ktrdr/cli/async_cli_client.py`
**Type:** CODING
**Task Categories:** -

**Description:**
Delete the old async CLI client file.

**Pre-check:**
```bash
grep -r "from ktrdr.cli.async_cli_client" ktrdr/
# Should return nothing
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] No imports remain

---

## Task 5.2: Delete api_client.py

**File(s):** `ktrdr/cli/api_client.py`
**Type:** CODING
**Task Categories:** -

**Description:**
Delete the old sync API client file. Also remove `get_api_client()` helper if it exists elsewhere.

**Pre-check:**
```bash
grep -r "from ktrdr.cli.api_client" ktrdr/
grep -r "get_api_client" ktrdr/
# Should return nothing
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] `get_api_client()` removed if exists
- [ ] No imports remain

---

## Task 5.3: Delete operation_executor.py

**File(s):** `ktrdr/cli/operation_executor.py`
**Type:** CODING
**Task Categories:** -

**Description:**
Delete the old operation executor file.

**Pre-check:**
```bash
grep -r "from ktrdr.cli.operation_executor" ktrdr/
# Should return nothing
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] No imports remain

---

## Task 5.4: Post-Deletion Verification

**Type:** TESTING
**Task Categories:** E2E

**Description:**
After deleting old client files, verify that nothing broke. This confirms the deletions were safe.

**Commands to test (ALL API-based commands):**

```bash
# =============================================================================
# SYNC COMMANDS
# =============================================================================

ktrdr data show AAPL --start 2024-01-01
ktrdr data range AAPL
ktrdr data load AAPL --timeframe 1h --start 2024-01-01 --end 2024-03-31

ktrdr indicators list
ktrdr indicators compute AAPL 1d RSI

ktrdr strategies list
ktrdr strategies validate strategies/v3_minimal.yaml

ktrdr operations list

ktrdr fuzzy config validate --config config/fuzzy.yaml

ktrdr ib status
ktrdr ib test

# =============================================================================
# ASYNC COMMANDS
# =============================================================================

ktrdr checkpoints show test_op_123

ktrdr agent status
ktrdr agent budget

# =============================================================================
# OPERATION COMMANDS
# =============================================================================

ktrdr models train strategies/v3_minimal.yaml --start-date 2024-01-01 --end-date 2024-03-31

ktrdr backtest run v3_minimal EURUSD 1h --start-date 2024-01-01 --end-date 2024-03-31

ktrdr dummy dummy
```

**Process:**
1. Run all commands from Task 5.0
2. Verify no import errors or missing module issues
3. Verify all long-running operations complete
4. If anything fails, the deletion broke something — investigate

**Acceptance Criteria:**
- [ ] No import errors related to deleted files
- [ ] All sync commands work
- [ ] All async commands work
- [ ] All operation commands complete successfully
- [ ] `make test-unit` passes
- [ ] `make quality` passes

---

## Completion Checklist

- [ ] **Task 5.0: Pre-deletion E2E passed** (all commands work before we touch anything)
- [ ] All old client files deleted (Tasks 5.1-5.3)
- [ ] `make test-unit` passes
- [ ] `make quality` passes
- [ ] Grep finds no references to deleted files
- [ ] **Task 5.4: Post-deletion verification passed** (nothing broke)

---

## Success Criteria (Overall Project)

1. ✅ Single `ktrdr/cli/client/` module handles all CLI HTTP needs
2. ✅ All existing CLI tests pass
3. ✅ No user-facing behavior changes
4. ✅ ~500-700 lines of code removed
5. ✅ URL handling in exactly one place
