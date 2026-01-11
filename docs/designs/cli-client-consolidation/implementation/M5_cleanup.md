---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Cleanup

**Branch:** `feature/cli-client-consolidation-m5`
**Builds on:** M2, M3, M4
**Goal:** Old client code deleted. Single source of truth.

## E2E Test Scenario

```bash
# Verify no references to old clients
grep -r "from ktrdr.cli.async_cli_client" ktrdr/
grep -r "from ktrdr.cli.api_client" ktrdr/
grep -r "from ktrdr.cli.operation_executor" ktrdr/

# Should return nothing

# Verify all tests pass
make test-unit
make quality

# FULL E2E: Run all commands and verify SUCCESS (see Task 5.4)
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
**Estimated time:** 2-4 hours (including wait time for long operations)
**Task Categories:** E2E

**Description:**
Before deleting any old client files, verify ALL migrated CLI commands work correctly with the new unified client. This establishes a baseline — if anything fails here, fix it before proceeding with deletion.

**Prerequisites (ask user to ensure before starting):**
- IB host service running and connected
- Docker environment running (`docker compose up`)
- Market data available for test symbols

**Commands to test (must ALL succeed):**

```bash
# === SYNC COMMANDS (M2) ===

# Data commands
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr data get-range AAPL 1d

# Indicator commands
ktrdr indicators list
ktrdr indicators info RSI

# Strategy commands
ktrdr strategies list
ktrdr strategies validate strategies/v3_minimal.yaml

# Operations commands
ktrdr operations list

# Fuzzy commands
ktrdr fuzzy list-sets

# IB commands (if IB host service available)
ktrdr ib status

# === ASYNC COMMANDS (M3) ===

# Checkpoint commands
ktrdr checkpoints list

# === OPERATION COMMANDS (M4) ===

# Training (wait for completion)
ktrdr models train strategies/v3_minimal.yaml --start-date 2024-01-01 --end-date 2024-03-31

# Backtest (wait for completion)
ktrdr backtest run v3_minimal EURUSD 1h --start-date 2024-01-01 --end-date 2024-03-31
```

**Process:**
1. Ask user: "Please ensure Docker is running and IB host service is available"
2. Run each command category and verify success
3. For long-running operations (training, backtest), wait for actual completion
4. If any command fails, investigate and fix BEFORE proceeding to deletion tasks
5. Document all results

**Acceptance Criteria:**
- [ ] All sync commands succeed (data, indicators, strategies, operations, fuzzy, ib)
- [ ] All async commands succeed (checkpoints)
- [ ] Training completes successfully (not just starts)
- [ ] Backtest completes successfully (not just starts)
- [ ] No commands fail due to client issues
- [ ] Results documented

**If any test fails:** Stop. Do not proceed to Task 5.1. Fix the issue first.

---

## Task 5.1: Delete async_cli_client.py

**File(s):** `ktrdr/cli/async_cli_client.py`
**Type:** CODING
**Estimated time:** 30 minutes
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
**Estimated time:** 30 minutes
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
**Estimated time:** 30 minutes
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
**Estimated time:** 30-60 minutes
**Task Categories:** E2E

**Description:**
After deleting old client files, verify that nothing broke. This is a confirmation that the deletions were safe — Task 5.0 already verified functionality, so this is a sanity check.

**Commands to test (same as Task 5.0, abbreviated):**

```bash
# Quick sync command checks
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr indicators list
ktrdr strategies list
ktrdr operations list

# Quick async command check
ktrdr checkpoints list

# One operation command (training is faster than backtest)
ktrdr models train strategies/v3_minimal.yaml --start-date 2024-01-01 --end-date 2024-03-31
```

**Process:**
1. Run representative commands from each category
2. Verify no import errors or missing module issues
3. Verify at least one long-running operation still works
4. If anything fails, the deletion broke something — investigate

**Acceptance Criteria:**
- [ ] No import errors related to deleted files
- [ ] Representative sync commands work
- [ ] Representative async commands work
- [ ] At least one operation command completes successfully
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
