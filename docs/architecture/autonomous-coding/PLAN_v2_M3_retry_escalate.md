---
design: docs/architecture/autonomous-coding/DESIGN_v2_haiku_brain.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE_v2_haiku_brain.md
---

# Milestone 3: Retry/Escalate via Haiku

**Branch:** `feature/orchestrator-v2-m3-retry-escalate`
**Builds on:** M2 (Result Interpretation)
**Capability:** Intelligent retry decisions with guidance

## Tasks

### Task 3.1: Add should_retry_or_escalate() to HaikuBrain

**File:** `orchestrator/haiku_brain.py`
**Type:** CODING

**Description:**
Add the retry/escalate decision method. Uses Prompt 3 from architecture doc. Returns guidance for retry attempts.

**Implementation Notes:**

- Takes attempt history as list of summaries
- Returns `RetryDecision` with `guidance_for_retry`
- Contextual reasoning, not hardcoded rules
- Haiku decides based on error patterns, not just count

**Code to add:**

```python
@dataclass
class RetryDecision:
    decision: Literal["retry", "escalate"]
    reason: str
    guidance_for_retry: str | None  # Suggestion for next attempt

RETRY_ESCALATE_PROMPT = """You are deciding whether to retry a failed task or escalate to a human.

Task: {task_id} - {task_title}

Attempt history:
{attempt_history}

Current attempt count: {attempt_count}

Decide: Should we retry or escalate?

RETRY when:
- The error is different from previous attempts (making progress)
- The error seems transient or fixable (import errors, typos, missing files)
- Only 1-2 attempts so far and the errors aren't identical

ESCALATE when:
- Same or very similar error 3+ times (stuck in a loop)
- The error indicates a design/architecture issue, not a coding bug
- Claude explicitly said it needs human input or is confused
- The error is about something Claude can't fix (permissions, external service, missing context)

Return a JSON object:
{{
  "decision": "retry" | "escalate",
  "reason": "Brief explanation of why",
  "guidance_for_retry": "If retrying, what to tell Claude differently (null if escalating)"
}}

Return ONLY the JSON, no other text.
"""

class HaikuBrain:
    # ... existing code ...

    def should_retry_or_escalate(
        self,
        task_id: str,
        task_title: str,
        attempt_history: list[str],
        attempt_count: int,
    ) -> RetryDecision:
        """Decide whether to retry a failed task or escalate to human.
        Returns guidance_for_retry when retrying to help next attempt.
        """
        prompt = RETRY_ESCALATE_PROMPT.format(
            task_id=task_id,
            task_title=task_title,
            attempt_history="\n".join(f"Attempt {i+1}: {h}" for i, h in enumerate(attempt_history)),
            attempt_count=attempt_count,
        )
        response = self._invoke_haiku(prompt)
        return self._parse_retry_decision(response)

    def _parse_retry_decision(self, response: str) -> RetryDecision:
        data = self._extract_json(response)
        return RetryDecision(
            decision=data["decision"],
            reason=data.get("reason", ""),
            guidance_for_retry=data.get("guidance_for_retry"),
        )
```

**Tests:** `orchestrator/tests/test_haiku_brain.py`

- Test: First failure with fixable error → retry with guidance
- Test: Same error 3x → escalate
- Test: Different errors each time → retry (making progress)
- Test: Error says "I need clarification" → escalate
- Test: Architecture issue mentioned → escalate

**Acceptance Criteria:**

- [ ] `should_retry_or_escalate()` returns `RetryDecision`
- [ ] `guidance_for_retry` populated when decision is retry
- [ ] Contextual decisions based on error content
- [ ] Unit tests pass

---

### Task 3.2: Wire retry decision to task execution loop

**File:** `orchestrator/task_runner.py`
**Type:** CODING

**Description:**
Replace LoopDetector usage with HaikuBrain retry decisions. Pass `guidance_for_retry` to the next attempt.

**Implementation Notes:**

- Remove `LoopDetector` import and instantiation
- Remove calls to `loop_detector.should_stop_task()` and `loop_detector.record_task_failure()`
- After failed task interpretation, call `brain.should_retry_or_escalate()`
- If retry: append `guidance_for_retry` to `human_guidance` for next attempt
- If escalate: trigger escalation flow
- Track attempt history in state (already exists: `state.attempt_history`)

**Code changes:**

```python
# Before (in run_task_with_escalation):
should_stop, reason = loop_detector.should_stop_task(task.id)
if should_stop:
    # ... handle loop detection

# After task fails:
loop_detector.record_task_failure(task.id, result.error or "Unknown error")

# After:
# Remove loop_detector entirely

# When task fails:
if result.status == "failed":
    # Record in attempt history
    attempt_summary = f"Failed: {result.error or 'Unknown error'}"
    if task.id not in state.attempt_history:
        state.attempt_history[task.id] = []
    state.attempt_history[task.id].append(attempt_summary)

    # Ask Haiku what to do
    decision = brain.should_retry_or_escalate(
        task_id=task.id,
        task_title=task.title,
        attempt_history=state.attempt_history[task.id],
        attempt_count=len(state.attempt_history[task.id]),
    )

    if decision.decision == "retry":
        console.print(f"Retrying: {decision.reason}")
        if decision.guidance_for_retry:
            console.print(f"Guidance: {decision.guidance_for_retry}")
        guidance = decision.guidance_for_retry
        # Loop continues with guidance
    else:
        console.print(f"Escalating: {decision.reason}")
        # Trigger escalation
        info = EscalationInfo(
            task_id=task.id,
            question=f"Task failed after {len(state.attempt_history[task.id])} attempts: {decision.reason}",
            options=None,
            recommendation=None,
            raw_output=result.output,
        )
        response = await escalate_and_wait(info, tracer, notify)
        guidance = response
```

**Acceptance Criteria:**

- [ ] LoopDetector removed from task execution
- [ ] HaikuBrain makes retry/escalate decisions
- [ ] `guidance_for_retry` passed to retry attempts
- [ ] Escalation triggered when Haiku says escalate
- [ ] Attempt history tracked correctly

---

### Task 3.3: Delete loop_detector.py

**File:** `orchestrator/loop_detector.py`
**Type:** CODING

**Description:**
Delete the hardcoded loop detection module.

**Implementation Notes:**

- Remove file entirely
- Update all imports
- `LoopDetectorConfig` no longer needed
- `LoopDetector` class no longer needed
- Run `grep -r "from orchestrator.loop_detector" orchestrator/` to find imports

**Files to check:**

- `orchestrator/task_runner.py`
- `orchestrator/milestone_runner.py`

**Acceptance Criteria:**

- [ ] `loop_detector.py` deleted
- [ ] All imports updated
- [ ] No broken imports

---

### Task 3.4: M3 E2E Test

**Type:** VERIFICATION

**Description:**
Verify intelligent retry decisions with guidance.

**Test Steps:**

```bash
# 1. Run unit tests
uv run pytest orchestrator/tests/test_haiku_brain.py -v -k "retry"

# 2. Test retry decision logic
uv run python -c "
from orchestrator.haiku_brain import HaikuBrain

brain = HaikuBrain()

# Test 1: First failure - should retry
result = brain.should_retry_or_escalate(
    task_id='1.1',
    task_title='Create data model',
    attempt_history=['Failed: ImportError - no module named pandas'],
    attempt_count=1,
)
print(f'Test 1 - First failure: decision={result.decision}, guidance={result.guidance_for_retry}')
assert result.decision == 'retry', f'Expected retry, got {result.decision}'
assert result.guidance_for_retry is not None, 'Expected guidance for retry'

# Test 2: Same error 3x - should escalate
result = brain.should_retry_or_escalate(
    task_id='1.1',
    task_title='Create data model',
    attempt_history=[
        'Failed: ImportError - no module named pandas',
        'Failed: ImportError - no module named pandas',
        'Failed: ImportError - no module named pandas',
    ],
    attempt_count=3,
)
print(f'Test 2 - Same error 3x: decision={result.decision}')
assert result.decision == 'escalate', f'Expected escalate, got {result.decision}'

# Test 3: Different errors - making progress, should retry
result = brain.should_retry_or_escalate(
    task_id='1.1',
    task_title='Create data model',
    attempt_history=[
        'Failed: ImportError - no module named pandas',
        'Failed: TypeError - expected str, got int',
    ],
    attempt_count=2,
)
print(f'Test 3 - Different errors: decision={result.decision}')
assert result.decision == 'retry', f'Expected retry, got {result.decision}'

print('SUCCESS: All retry decision tests passed')
"

# 3. Quality gates
make quality
```

**Success Criteria:**

- [ ] Retry decisions are contextual (not just count-based)
- [ ] `guidance_for_retry` provides useful suggestions
- [ ] Same error repeatedly → escalate
- [ ] Different errors → retry (making progress)
- [ ] Unit tests pass
- [ ] Quality gates pass

---

## Milestone 3 Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/test_haiku_brain.py -k retry`
- [ ] E2E test passes (Task 3.4)
- [ ] Previous M1 and M2 tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] `loop_detector.py` deleted
- [ ] Branch ready for merge: `feature/orchestrator-v2-m3-retry-escalate`
