---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Fail Loudly on Infrastructure Errors

**Branch:** `feature/v2.5-m1-fail-loudly`

**Goal:** Infrastructure errors (training data issues, backtest failures, etc.) should raise exceptions and fail the operation visibly — not return zeros or continue silently.

---

## E2E Test Scenario

**Purpose:** Verify infrastructure errors fail loudly and don't record to memory

```bash
# Prerequisites: Backend running

# 1. Count experiments before
BEFORE=$(ls memory/experiments/*.yaml 2>/dev/null | wc -l)

# 2. Trigger research that will hit infrastructure error
# (Use current broken multi-symbol config)
curl -X POST http://localhost:8000/api/v1/agent/trigger

OP_ID=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.operation_id')

# 3. Poll until operation completes
for i in {1..60}; do
  STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq -r '.data.status')
  if [ "$STATUS" = "failed" ] || [ "$STATUS" = "completed" ]; then break; fi
  sleep 2
done

# 4. Assert operation FAILED with error message
curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq '{status: .data.status, error: .data.error_message}'
# Expected: {"status": "failed", "error": "...meaningful error..."}

# 5. Assert NO new experiment in memory
AFTER=$(ls memory/experiments/*.yaml 2>/dev/null | wc -l)
[ "$AFTER" -eq "$BEFORE" ] && echo "PASS: No experiment recorded" || echo "FAIL: Experiment was recorded"
```

**Success Criteria:**
- [ ] Operation status is `failed`
- [ ] error_message describes what went wrong
- [ ] No new experiment in `memory/experiments/`

---

## Task 1.1: Audit Pipeline for Silent Failures

**Type:** RESEARCH
**Estimated time:** 2 hours

**What to do:**

Search the codebase for patterns that silently swallow errors or return fake results:

```bash
# Find silent zero returns
grep -rn "return.*0\.0" ktrdr/training/ ktrdr/backtesting/
grep -rn "return.*\[\]" ktrdr/training/ ktrdr/backtesting/

# Find log-and-continue patterns
grep -rn "logger.warning.*return" ktrdr/training/ ktrdr/backtesting/
grep -rn "logger.error.*return" ktrdr/training/ ktrdr/backtesting/

# Find empty exception handlers
grep -rn "except.*pass" ktrdr/training/ ktrdr/backtesting/
```

**Known locations (from investigation):**

1. `ktrdr/training/training_pipeline.py` ~line 668-676: X_test=None returns zeros
2. (Find others during audit)

**Deliverable:**

List of locations that need to be converted to exceptions:

| File | Line | Current Behavior | Should Be |
|------|------|------------------|-----------|
| training_pipeline.py | 668 | Returns zeros when X_test=None | Raise TrainingDataError |
| ... | ... | ... | ... |

**Acceptance Criteria:**

- [ ] All silent failure patterns documented
- [ ] Priority order established (which to fix first)

---

## Task 1.2: Define Pipeline Exception Types

**File:** `ktrdr/training/exceptions.py` (create)
**Type:** CODING
**Estimated time:** 45 min

**What to do:**

Create exception module for pipeline errors:

```python
# ktrdr/training/exceptions.py

class PipelineError(Exception):
    """Base class for pipeline infrastructure errors.

    These are bugs to fix, not experiments to learn from.
    They should fail operations visibly.
    """
    pass


class TrainingDataError(PipelineError):
    """Raised when training cannot produce valid data.

    Examples:
    - X_test is None (data pipeline failed)
    - Feature alignment produced empty result
    - Train/test split failed
    """
    pass


class BacktestDataError(PipelineError):
    """Raised when backtest cannot run due to data issues.

    Examples:
    - No price data for symbol
    - Feature mismatch between training and backtest
    """
    pass


class ModelLoadError(PipelineError):
    """Raised when model cannot be loaded for backtest.

    Examples:
    - Model file not found
    - Model format incompatible
    """
    pass
```

Also create `ktrdr/backtesting/exceptions.py` if backtest-specific exceptions are needed.

**Tests:**

- Unit: `tests/unit/training/test_exceptions.py`
  - [ ] All exceptions importable
  - [ ] Inheritance hierarchy correct
  - [ ] Messages preserved

**Acceptance Criteria:**

- [ ] Exception types cover all audited failure modes
- [ ] Clear docstrings explain when each is raised

---

## Task 1.3: Convert Silent Failures to Exceptions

**Files:** Various (from Task 1.1 audit)
**Type:** CODING
**Estimated time:** 2-3 hours

**What to do:**

For each location identified in Task 1.1, convert silent failure to exception.

**Example 1: training_pipeline.py ~line 668**

```python
# BEFORE
if X_test is None or y_test is None:
    logger.warning("No test data provided - returning zero metrics")
    return {"test_accuracy": 0.0, ...}

# AFTER
from ktrdr.training.exceptions import TrainingDataError

if X_test is None or y_test is None:
    raise TrainingDataError(
        "Training produced no test data. "
        "This usually indicates a data pipeline issue with multi-symbol "
        "or multi-timeframe configurations."
    )
```

**Example 2: backtest_runner.py (if applicable)**

```python
# BEFORE
if len(price_data) == 0:
    logger.warning("No price data")
    return {"total_trades": 0, ...}

# AFTER
from ktrdr.backtesting.exceptions import BacktestDataError

if len(price_data) == 0:
    raise BacktestDataError(
        f"No price data available for {symbol}. "
        "Check data cache and date range."
    )
```

**For each conversion:**
- Remove log-and-return pattern
- Add appropriate exception with helpful message
- Update any tests that expected the old behavior

**Tests:**

- Unit: Update existing tests to expect exceptions
- Unit: Add tests for each new exception path

**Acceptance Criteria:**

- [ ] All audited silent failures converted to exceptions
- [ ] Exception messages include actionable guidance
- [ ] No more silent zeros returned

---

## Task 1.4: Verify Exceptions Propagate to Operation Status

**File:** `ktrdr/agents/workers/research_worker.py` (verify)
**Type:** CODING
**Estimated time:** 1 hour

**What to do:**

Verify that when pipeline exceptions are raised:
1. They propagate up to the research worker
2. The operation status becomes FAILED
3. The error_message contains exception details

Check the existing error handling (around lines 530-545):

```python
# Current pattern - verify it catches PipelineError
if training_op.status == OperationStatus.FAILED:
    raise WorkerError(f"Training failed: {training_op.error_message}")
```

If needed, ensure PipelineError subclasses are caught and converted properly.

**Tests:**

- Integration: `tests/integration/agent_tests/test_error_propagation.py`
  - [ ] TrainingDataError → operation status=FAILED
  - [ ] BacktestDataError → operation status=FAILED
  - [ ] error_message contains exception details
  - [ ] No experiment recorded

**Smoke Test:**

```bash
# After triggering an error scenario
curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq '{status: .data.status, error: .data.error_message}'
# Should show: {"status": "failed", "error": "...meaningful error..."}
```

**Acceptance Criteria:**

- [ ] All PipelineError subclasses fail the operation
- [ ] error_message visible in operation details
- [ ] No experiment recorded to memory

---

## Milestone 1 Completion Checklist

- [ ] Task 1.1: Silent failure audit complete
- [ ] Task 1.2: Exception types defined
- [ ] Task 1.3: Silent failures converted to exceptions
- [ ] Task 1.4: Error propagation verified
- [ ] E2E test passes (above scenario)
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Code committed to branch: `feature/v2.5-m1-fail-loudly`

---

## Notes

**Why audit first?** We don't know all the silent failure locations. Task 1.1 finds them systematically before we start fixing.

**Scope:** This milestone fixes the "fail loudly" behavior. It does NOT fix the underlying bugs (multi-symbol, multi-TF). Those are M4 and M5.

**Dependency:** None - this is the first milestone

**Next:** M2 (Gate Rejection → Memory) uses the clear distinction between infrastructure errors (exceptions) and gate rejections (valid experiments with poor results)
