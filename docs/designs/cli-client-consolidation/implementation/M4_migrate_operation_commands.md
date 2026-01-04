---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Migrate Operation Commands

**Branch:** `feature/cli-client-consolidation-m4`
**Builds on:** M1
**Goal:** Commands using `AsyncOperationExecutor` now use `AsyncCLIClient.execute_operation()`.

## E2E Test Scenario

```bash
# Verify operation commands work with progress
ktrdr model train <args>  # Should show progress, complete successfully

# Verify cancellation
ktrdr model train <args>  # Press Ctrl+C, should cancel cleanly
```

**Success Criteria:**
- [ ] Progress displays correctly
- [ ] Cancellation works
- [ ] No imports from `operation_executor.py`

---

## Migration Pattern

```python
# Before
from ktrdr.cli.operation_executor import AsyncOperationExecutor
executor = AsyncOperationExecutor()
result = await executor.execute(adapter)

# After
from ktrdr.cli.client import AsyncCLIClient
async with AsyncCLIClient() as client:
    result = await client.execute_operation(adapter, on_progress=callback)
```

---

## Task 4.1: Migrate model_commands.py (training)

**File(s):** `ktrdr/cli/model_commands.py`
**Type:** CODING
**Estimated time:** 2 hours
**Task Categories:** Cross-Component, Background/Async, State Machine

**Description:**
Replace `AsyncOperationExecutor` with `AsyncCLIClient.execute_operation()` for training commands.

**Testing Requirements:**

*Smoke Test:*
```bash
# Start training, verify progress displays
ktrdr model train <args>

# Start training, press Ctrl+C, verify clean cancellation
ktrdr model train <args>
```

**Acceptance Criteria:**
- [ ] No imports from `operation_executor.py`
- [ ] Progress displays correctly
- [ ] Ctrl+C cancels operation

---

## Task 4.2: Migrate backtest_commands.py

**File(s):** `ktrdr/cli/backtest_commands.py`
**Type:** CODING
**Estimated time:** 2 hours
**Task Categories:** Cross-Component, Background/Async, State Machine

**Description:**
Replace `AsyncOperationExecutor` with `AsyncCLIClient.execute_operation()` for backtest commands.

**Testing Requirements:**

*Smoke Test:*
```bash
# Start backtest, verify progress displays
ktrdr backtest run <args>

# Start backtest, press Ctrl+C, verify clean cancellation
ktrdr backtest run <args>
```

**Acceptance Criteria:**
- [ ] No imports from `operation_executor.py`
- [ ] Progress displays correctly
- [ ] Ctrl+C cancels operation

---

## Completion Checklist

- [ ] Training and backtest commands migrated
- [ ] No imports from `operation_executor.py`
- [ ] Progress display works
- [ ] Cancellation works
- [ ] All existing tests pass
