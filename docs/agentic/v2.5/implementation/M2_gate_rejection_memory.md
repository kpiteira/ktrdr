---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Gate Rejection → Memory

**Branch:** `feature/v2.5-m2-gate-rejection`
**Depends on:** M1 (fail loudly)

**Goal:** When training gate rejects (valid training but poor results), route to AssessmentWorker and record partial experiment to memory for learning.

---

## E2E Test Scenario

**Purpose:** Verify gate rejection records experiment with partial results

```bash
# Prerequisites: Backend running, stub workers

# 1. Count experiments before
BEFORE=$(ls memory/experiments/*.yaml 2>/dev/null | wc -l)

# 2. Trigger research (with stub that produces low accuracy)
# Need to configure stub to return e.g. 5% accuracy
curl -X POST http://localhost:8000/api/v1/agent/trigger

OP_ID=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.child_operation_id // .operation_id')

# 3. Poll until cycle completes
for i in {1..120}; do
  PHASE=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.phase')
  if [ "$PHASE" = "idle" ]; then break; fi
  sleep 2
done

# 4. Check experiment was saved
AFTER=$(ls memory/experiments/*.yaml 2>/dev/null | wc -l)
[ "$AFTER" -gt "$BEFORE" ] && echo "PASS: Experiment recorded" || echo "FAIL: No experiment"

# 5. Check experiment status
LATEST=$(ls -t memory/experiments/*.yaml | head -1)
cat "$LATEST" | grep -E "^status:"
# Expected: status: gate_rejected_training

cat "$LATEST" | grep -E "^gate_rejection_reason:"
# Expected: gate_rejection_reason: accuracy_too_low (5% < 10%)

cat "$LATEST" | grep -E "^backtest_result:"
# Expected: backtest_result: null (or not present)
```

**Success Criteria:**
- [ ] Experiment saved to `memory/experiments/`
- [ ] `status: gate_rejected_training`
- [ ] `gate_rejection_reason` is set
- [ ] `backtest_result` is null/None
- [ ] `training_result` is present with metrics

---

## Task 2.1: Add Status Fields to ExperimentRecord

**File:** `ktrdr/agents/memory.py`
**Type:** CODING
**Estimated time:** 1 hour

**What to do:**

Add new fields to ExperimentRecord for tracking gate rejections:

```python
@dataclass
class ExperimentRecord:
    id: str
    timestamp: datetime
    strategy_name: str
    context: ExperimentContext
    training_result: dict  # Always present for recorded experiments
    backtest_result: dict | None  # None if gate rejected after training
    assessment: Assessment | None
    source: str

    # NEW fields
    status: str = "completed"  # "completed", "gate_rejected_training", "gate_rejected_backtest"
    gate_rejection_reason: str | None = None  # e.g., "accuracy_too_low (8% < 10%)"
```

Update serialization/deserialization to handle new fields. Ensure backward compatibility - old experiments without status field default to "completed".

**Tests:**

- Unit: `tests/unit/agent_tests/test_memory.py`
  - [ ] ExperimentRecord with status field serializes correctly
  - [ ] ExperimentRecord with gate_rejection_reason serializes correctly
  - [ ] Old experiments without status field load as "completed"
  - [ ] backtest_result=None serializes correctly

**Acceptance Criteria:**

- [ ] ExperimentRecord has `status` and `gate_rejection_reason` fields
- [ ] YAML serialization includes new fields
- [ ] Backward compatible with existing experiments

---

## Task 2.2: Update AssessmentWorker Signature

**File:** `ktrdr/agents/workers/assessment_worker.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**What to do:**

Update AssessmentWorker.run() to accept partial results and gate rejection info:

```python
async def run(
    self,
    operation_id: str,
    training_result: dict,
    backtest_result: dict | None = None,  # None for training gate rejections
    gate_rejection_reason: str | None = None,
) -> dict:
    """Assess experiment and save to memory.

    Handles both successful experiments and gate rejections.
    For gate rejections, backtest_result is None and we record
    the experiment with status=gate_rejected_*.
    """
    # Determine status
    if gate_rejection_reason:
        if backtest_result is None:
            status = "gate_rejected_training"
        else:
            status = "gate_rejected_backtest"
    else:
        status = "completed"

    # LLM analysis (works with partial results)
    assessment = await self._analyze_results(training_result, backtest_result)

    # Save experiment with appropriate status
    record = ExperimentRecord(
        id=generate_experiment_id(),
        timestamp=datetime.now(),
        strategy_name=self.strategy_name,
        context=self._build_context(),
        training_result=training_result,
        backtest_result=backtest_result,
        assessment=assessment,
        source="agent",
        status=status,
        gate_rejection_reason=gate_rejection_reason,
    )
    self.memory.save_experiment(record)
```

Also update `_analyze_results()` to handle partial data gracefully.

**Tests:**

- Unit: `tests/unit/agent_tests/test_assessment_worker.py`
  - [ ] run() with backtest_result=None saves correctly
  - [ ] run() with gate_rejection_reason sets status correctly
  - [ ] LLM analysis handles missing backtest results
  - [ ] Experiment saved with all fields

**Acceptance Criteria:**

- [ ] AssessmentWorker accepts optional backtest_result
- [ ] Gate rejection reason propagates to saved experiment
- [ ] Status field set correctly based on inputs

---

## Task 2.3: Update Research Worker State Machine

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 2 hours

**What to do:**

Modify the state machine so gate rejection transitions to ASSESSING instead of FAILED.

Find the training gate check (around lines 530-536):

```python
# BEFORE (current behavior)
if not gate_passed:
    raise GateError(f"Training gate failed: {gate_reason}")
    # This causes cycle to fail without assessment
```

Change to:

```python
# AFTER (new behavior)
if not gate_passed:
    # Don't raise - transition to ASSESSING with partial results
    self._gate_rejection_reason = gate_reason
    self._skip_backtest = True
    # Phase will transition to ASSESSING, not BACKTESTING
```

Then modify the phase transition logic:

```python
# After training completes
if gate_passed:
    # Normal flow: start backtest
    await self._start_backtest(operation_id)
    self._set_phase("backtesting")
else:
    # Gate rejection: skip to assessment with partial results
    await self._start_assessment(
        operation_id,
        training_result=self._training_result,
        backtest_result=None,
        gate_rejection_reason=self._gate_rejection_reason,
    )
    self._set_phase("assessing")
```

Similarly for backtest gate rejection - pass full results but with gate_rejection_reason.

**Tests:**

- Integration: `tests/integration/agent_tests/test_gate_rejection_flow.py`
  - [ ] Training gate rejection → phase becomes "assessing" (not "failed")
  - [ ] Training gate rejection → AssessmentWorker called with backtest_result=None
  - [ ] Backtest gate rejection → AssessmentWorker called with full results + rejection reason
  - [ ] Experiment saved with correct status

**Acceptance Criteria:**

- [ ] Gate rejection does NOT raise GateError
- [ ] Phase transitions to ASSESSING on gate rejection
- [ ] AssessmentWorker receives correct parameters
- [ ] Backtest skipped for training gate rejection

---

## Task 2.4: Update _start_assessment Method

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 1 hour

**What to do:**

Update `_start_assessment()` to accept new parameters:

```python
async def _start_assessment(
    self,
    operation_id: str,
    training_result: dict,
    backtest_result: dict | None = None,
    gate_rejection_reason: str | None = None,
) -> None:
    """Start assessment phase.

    For gate rejections, backtest_result may be None.
    """
    # Pass all parameters to assessment worker
    result = await self.assessment_worker.run(
        operation_id=operation_id,
        training_result=training_result,
        backtest_result=backtest_result,
        gate_rejection_reason=gate_rejection_reason,
    )
    # ... rest of method
```

**Tests:**

- Unit: `tests/unit/agent_tests/test_research_worker.py`
  - [ ] _start_assessment accepts optional parameters
  - [ ] Parameters passed correctly to assessment worker

**Acceptance Criteria:**

- [ ] Method signature updated
- [ ] Parameters forwarded to AssessmentWorker

---

## Task 2.5: E2E Test for Gate Rejection

**File:** `tests/e2e/agent/test_gate_rejection_e2e.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**What to do:**

Create E2E test that verifies the full gate rejection → memory flow:

```python
import pytest
from pathlib import Path

@pytest.mark.e2e
async def test_training_gate_rejection_records_experiment():
    """Gate rejection records experiment with partial results."""
    # Setup: Configure stub to return low accuracy
    # (may need env var or test fixture)

    # Count experiments before
    experiments_dir = Path("memory/experiments")
    before_count = len(list(experiments_dir.glob("*.yaml")))

    # Trigger research
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_URL}/api/v1/agent/trigger")
        assert resp.status_code == 200

    # Poll until idle
    for _ in range(120):
        resp = await client.get(f"{BACKEND_URL}/api/v1/agent/status")
        if resp.json().get("phase") == "idle":
            break
        await asyncio.sleep(2)

    # Verify experiment was saved
    after_count = len(list(experiments_dir.glob("*.yaml")))
    assert after_count > before_count, "No experiment recorded"

    # Verify experiment content
    latest = max(experiments_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        exp = yaml.safe_load(f)

    assert exp["status"] == "gate_rejected_training"
    assert exp["gate_rejection_reason"] is not None
    assert exp["training_result"] is not None
    assert exp.get("backtest_result") is None
```

**Acceptance Criteria:**

- [ ] Test triggers gate rejection scenario
- [ ] Test verifies experiment saved with correct status
- [ ] Test verifies partial results (no backtest)

---

## Milestone 2 Completion Checklist

- [ ] Task 2.1: ExperimentRecord has status fields
- [ ] Task 2.2: AssessmentWorker accepts partial results
- [ ] Task 2.3: State machine routes gate rejection → ASSESSING
- [ ] Task 2.4: _start_assessment method updated
- [ ] Task 2.5: E2E test passes
- [ ] M1 E2E test still passes (no regression)
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Code committed to branch: `feature/v2.5-m2-gate-rejection`

---

## Notes

**Key architectural decision:** Gate rejection is NOT a failure. It's a valid experiment with poor results that should be recorded for learning.

**Dependency:** Requires M1 (TrainingDataError) to distinguish infrastructure errors from gate rejections.

**Next:** M3 (Baby Gates + Brief) sets the actual gate thresholds and adds brief parameter
