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
- [ ] Old files deleted
- [ ] No references remain
- [ ] All tests pass
- [ ] **All CLI commands complete successfully (Task 5.4)**

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

## Task 5.4: Full E2E Verification (All Commands Must Succeed)

**Type:** TESTING
**Estimated time:** 2-4 hours (including wait time for long operations)
**Task Categories:** E2E

**Description:**
Run ALL migrated CLI commands end-to-end and verify they complete successfully. This is not a smoke test - operations must succeed, not just start.

**Prerequisites (ask user to ensure before starting):**
- IB host service running and connected
- Anthropic API key configured
- Training infrastructure available

**Commands to test (must ALL succeed):**

```bash
# Data commands
ktrdr data load AAPL --timeframe 1d
ktrdr data show AAPL --timeframe 1d

# Indicator commands
ktrdr indicators list
ktrdr indicators compute AAPL RSI --timeframe 1d

# Strategy commands
ktrdr strategies list
ktrdr strategies validate strategies/v3_minimal.yaml

# Operations commands
ktrdr operations list

# Agent commands (long-running)
ktrdr agent status
ktrdr agent trigger --model haiku --monitor  # Wait for completion

# Model commands (long-running)
ktrdr models train strategies/v3_minimal.yaml AAPL  # Wait for completion
```

**Process:**
1. Before starting, ask user: "Please ensure IB host service is running and Anthropic API key is configured"
2. Run each command and wait for successful completion
3. If any command fails for infrastructure reasons, stop and ask user to fix
4. Do not proceed until all commands succeed
5. Document results

**Acceptance Criteria:**
- [ ] All data commands succeed
- [ ] All indicator commands succeed
- [ ] All strategy commands succeed
- [ ] All operations commands succeed
- [ ] Agent trigger completes successfully (not just starts)
- [ ] Model training completes successfully (not just starts)
- [ ] No commands fail due to client migration issues

---

## Completion Checklist

- [ ] All old client files deleted
- [ ] `make test-unit` passes
- [ ] `make quality` passes
- [ ] Grep finds no references to deleted files
- [ ] All CLI commands still work
- [ ] **Task 5.4: Full E2E verification passed (all commands succeeded)**

---

## Success Criteria (Overall Project)

1. ✅ Single `ktrdr/cli/client/` module handles all CLI HTTP needs
2. ✅ All existing CLI tests pass
3. ✅ No user-facing behavior changes
4. ✅ ~500-700 lines of code removed
5. ✅ URL handling in exactly one place
