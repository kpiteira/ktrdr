# M1 Audit: Implementation vs Architecture

**Date**: 2025-12-13
**Auditor**: Claude
**Status**: Issues Found

---

## Critical Issues

### 1. Polling Loop Pattern (Task 1.10 — already documented)

**Spec (ARCHITECTURE.md)**:
```python
while True:
    child_op = await self.ops.get_operation(child_op_id)
    if child_op.status == OperationStatus.COMPLETED:
        # advance to next phase
    await self._cancellable_sleep(300)  # poll every 5 min
```

**Actual**: Sequential awaits, no polling loop.

**Impact**: Won't work with real distributed workers.

---

## High Severity Issues

### 2. Missing Quality Gates

**Spec (ARCHITECTURE.md lines 340-380)**:
```python
def check_training_gate(result: dict) -> tuple[bool, str]:
    if result.get("accuracy", 0) < 0.45:
        return False, "accuracy_below_threshold"
    # ... more checks

def check_backtest_gate(result: dict) -> tuple[bool, str]:
    if result.get("win_rate", 0) < 0.45:
        return False, "win_rate_too_low"
    # ... more checks
```

**Actual**: No gates implemented. Orchestrator proceeds regardless of results.

**Impact**: Bad strategies won't be filtered out.

**Fix**: Add gate checks between phases in orchestrator.

---

### 3. Cancellation Doesn't Propagate to Child

**Spec (ARCHITECTURE.md lines 197-206)**:
```python
except asyncio.CancelledError:
    child_op_id = self._get_current_child_op_id(op)
    if child_op_id:
        await self.ops.cancel_operation(child_op_id, "Parent cancelled")
    raise
```

**Actual**: Cancellation just logs and re-raises, doesn't cancel child.

**Impact**: Child operations left running when parent cancelled.

**Fix**: Add child cancellation in CancelledError handler.

---

## Medium Severity Issues

### 4. Missing `child_operation_id` in Status Response

**Spec (ARCHITECTURE.md lines 299-311)**:
```json
{
    "status": "active",
    "child_operation_id": "op_training_...",  // MISSING
    ...
}
```

**Actual**: Status response doesn't include child_operation_id.

**Impact**: Users can't see which child operation is running.

**Fix**: Add child_operation_id to status response.

---

### 5. Missing Results in Parent Metadata

**Spec (ARCHITECTURE.md lines 214-230)**:
```python
{
    "strategy_name": "momentum_rsi_v3",
    "strategy_path": "/app/strategies/momentum_rsi_v3.yaml",
    "training_result": {"accuracy": 0.62, ...},
    "backtest_result": {"sharpe_ratio": 1.2, ...},
    "assessment_verdict": "promising",
}
```

**Actual**: Only `phase` and child op IDs stored in metadata.

**Impact**: Can't query results from parent operation.

**Fix**: Store results in parent metadata after each phase completes.

---

### 6. Missing `assessment_path` in Stub Result

**Spec (ARCHITECTURE.md lines 245-258)**:
```python
{
    "assessment_path": "/app/strategies/momentum_rsi_v3/assessment.json",
    ...
}
```

**Actual**: StubAssessmentWorker doesn't return `assessment_path`.

**Impact**: Minor — stub only, but should match contract.

**Fix**: Add `assessment_path` to stub return value.

---

## Low Severity Issues

### 7. No Dedicated Cancel Endpoint

**Spec (ARCHITECTURE.md lines 328-336)**:
```
DELETE /agent/cancel
```

**Actual**: Comment says "use operations API: DELETE /operations/{op_id}"

**Impact**: Acceptable deviation — documented in endpoint file.

**Deliberate Choice**: Using existing operations API avoids duplication.

---

### 8. No CLI Cancel Command

**Spec (DESIGN.md line 137)**:
```
ktrdr agent cancel
```

**Actual**: Removed, using `ktrdr operations cancel <op_id>` instead.

**Impact**: Acceptable deviation — consistent with API decision.

**Deliberate Choice**: Using existing operations CLI avoids duplication.

---

## Summary

| Severity | Count | Issues |
|----------|-------|--------|
| Critical | 1 | Polling loop (Task 1.10) |
| High | 2 | Quality gates, cancellation propagation |
| Medium | 3 | child_operation_id, metadata results, assessment_path |
| Low | 2 | Cancel endpoint/CLI (deliberate deviations) |

---

## Recommended New Tasks

### Task 1.11: Implement Quality Gates

Add training and backtest gate checks to orchestrator.

### Task 1.12: Fix Cancellation Propagation

Cancel active child operation when parent is cancelled.

### Task 1.13: Complete Metadata Contract

- Add child_operation_id to status response
- Store phase results in parent metadata
- Add assessment_path to stub

---

## Deliberate Deviations (Acceptable)

1. **Cancel via operations API** — Avoids duplicating cancellation logic
2. **No dedicated agent cancel CLI** — Uses `ktrdr operations cancel`

These are documented and intentional simplifications.
