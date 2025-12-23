---
design: docs/architecture/autonomous-coding/DESIGN_v2_haiku_brain.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE_v2_haiku_brain.md
---

# Milestone 2: Result Interpretation via Haiku

**Branch:** `feature/orchestrator-v2-m2-interpretation`
**Builds on:** M1 (Haiku Brain + Plan Parsing)
**Capability:** Task status detected semantically without STATUS markers

## Tasks

### Task 2.1: Add interpret_result() to HaikuBrain

**File:** `orchestrator/haiku_brain.py`
**Type:** CODING

**Description:**
Add the `interpret_result()` method that determines task status from sandbox output. Uses Prompt 2 from architecture doc.

**Implementation Notes:**

- No output truncation (Decision 8)
- Return `InterpretationResult` dataclass
- Handle JSON parsing errors gracefully
- When in doubt, return `needs_help` (safer)
- Detect AskUserQuestion tool usage in output

**Code to add:**

```python
@dataclass
class InterpretationResult:
    status: Literal["completed", "failed", "needs_help"]
    summary: str
    error: str | None
    question: str | None
    options: list[str] | None
    recommendation: str | None

INTERPRET_RESULT_PROMPT = """Analyze this Claude Code output and determine the task status.

Return a JSON object:
{
  "status": "completed" | "failed" | "needs_help",
  "summary": "Brief description of what happened",
  "error": "Error details if failed, null otherwise",
  "question": "The question Claude is asking, if needs_help",
  "options": ["Option A", "Option B"] or null,
  "recommendation": "Claude's recommended option, if stated"
}

Determine status as:
- "completed": Task finished successfully. Look for task summaries, passing tests, successful commits.
- "failed": Task encountered an error it couldn't recover from.
- "needs_help": Claude is asking a question or needs human decision.

When in doubt between "completed" and "needs_help", prefer "needs_help".

Return ONLY the JSON, no other text.

Claude Code output:
{output}
"""

class HaikuBrain:
    # ... existing code ...

    def interpret_result(self, output: str) -> InterpretationResult:
        """Interpret Claude Code output to determine task status.
        No truncation - full output is sent to Haiku.
        """
        prompt = INTERPRET_RESULT_PROMPT.format(output=output)
        response = self._invoke_haiku(prompt)
        return self._parse_interpretation(response)

    def _parse_interpretation(self, response: str) -> InterpretationResult:
        data = self._extract_json(response)
        return InterpretationResult(
            status=data["status"],
            summary=data.get("summary", ""),
            error=data.get("error"),
            question=data.get("question"),
            options=data.get("options"),
            recommendation=data.get("recommendation"),
        )
```

**Tests:** `orchestrator/tests/test_haiku_brain.py`

- Test: Output with "## Task Complete: 1.1" summary → status=completed
- Test: Output with unresolved error → status=failed
- Test: Output with AskUserQuestion tool call → status=needs_help, question extracted
- Test: Ambiguous output → status=needs_help (conservative)
- Test: Large output (10k+ chars) → no truncation, works correctly

**Acceptance Criteria:**

- [ ] `interpret_result()` returns `InterpretationResult`
- [ ] No output truncation
- [ ] AskUserQuestion detected as needs_help
- [ ] Question and options extracted when present
- [ ] Unit tests pass

---

### Task 2.2: Replace task_runner interpretation with HaikuBrain

**File:** `orchestrator/task_runner.py`
**Type:** CODING

**Description:**
Replace the hybrid regex+LLM interpretation in `parse_task_output()` with pure HaikuBrain call.

**Implementation Notes:**

- Remove `parse_task_output()` function entirely
- Remove STATUS/ERROR/QUESTION/OPTIONS/RECOMMENDATION regex patterns
- Import HaikuBrain and use `interpret_result()`
- Map `InterpretationResult` fields to `TaskResult` fields
- HaikuBrain instance should be passed in or created once

**Code changes:**

```python
# Before (in run_task):
status, question, options, recommendation, error = parse_task_output(claude_result.result)

# After:
from orchestrator.haiku_brain import HaikuBrain

# In run_task or run_task_with_escalation:
interpretation = brain.interpret_result(claude_result.result)

return TaskResult(
    task_id=task.id,
    status=interpretation.status,
    duration_seconds=duration,
    tokens_used=tokens_used,
    cost_usd=claude_result.total_cost_usd,
    output=claude_result.result,
    session_id=claude_result.session_id,
    question=interpretation.question,
    options=interpretation.options,
    recommendation=interpretation.recommendation,
    error=interpretation.error,
)
```

**Acceptance Criteria:**

- [ ] `parse_task_output()` removed
- [ ] All regex patterns for STATUS/ERROR/QUESTION removed
- [ ] HaikuBrain used for all interpretation
- [ ] Existing task execution still works
- [ ] Escalation still triggers on needs_help

---

### Task 2.3: Delete llm_interpreter.py

**File:** `orchestrator/llm_interpreter.py`
**Type:** CODING

**Description:**
Delete the old LLM interpreter module. The functionality is now in HaikuBrain.

**Implementation Notes:**

- `find_claude_cli()` should already be in `haiku_brain.py` (from M1 Task 1.1)
- `strip_markdown()` can be deleted (Haiku handles formatting)
- `LLMInterpreter` class no longer needed
- Update all imports
- Run `grep -r "from orchestrator.llm_interpreter" orchestrator/` to find imports

**Files to check for imports:**

- `orchestrator/task_runner.py`
- `orchestrator/escalation.py`

**Acceptance Criteria:**

- [ ] `llm_interpreter.py` deleted
- [ ] `find_claude_cli()` available in haiku_brain.py
- [ ] All imports updated
- [ ] No broken imports

---

### Task 2.4: M2 E2E Test

**Type:** VERIFICATION

**Description:**
Verify that task status is detected semantically without STATUS markers.

**Test Steps:**

```bash
# 1. Run unit tests
uv run pytest orchestrator/tests/test_haiku_brain.py -v -k "interpret"

# 2. Test interpretation on real output
# Create a test script that feeds sample output to interpret_result

uv run python -c "
from orchestrator.haiku_brain import HaikuBrain

brain = HaikuBrain()

# Test 1: Completed task (without STATUS marker)
completed_output = '''
## Task Complete: 1.1

**What was implemented:**
- Created the data model

**Files changed:**
- models.py (created)

All tests passing.
'''

result = brain.interpret_result(completed_output)
print(f'Test 1 - Completed: status={result.status}')
assert result.status == 'completed', f'Expected completed, got {result.status}'

# Test 2: Needs help (AskUserQuestion)
needs_help_output = '''
I need clarification before proceeding.

Which authentication method should I use?

Options:
A) JWT tokens
B) API keys
C) OAuth

I recommend option A (JWT) as it matches the existing user service.
'''

result = brain.interpret_result(needs_help_output)
print(f'Test 2 - Needs help: status={result.status}, question={result.question}')
assert result.status == 'needs_help', f'Expected needs_help, got {result.status}'

print('SUCCESS: All interpretation tests passed')
"

# 3. Run a real task (optional - requires sandbox)
# uv run orchestrator task orchestrator/test_plans/health_check.md 1.1

# 4. Quality gates
make quality
```

**Success Criteria:**

- [ ] Task without explicit STATUS marker detected as completed
- [ ] AskUserQuestion in output triggers needs_help
- [ ] Question and options extracted correctly
- [ ] Unit tests pass
- [ ] Quality gates pass

---

## Milestone 2 Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/test_haiku_brain.py -k interpret`
- [ ] E2E test passes (Task 2.4)
- [ ] Previous M1 tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] `llm_interpreter.py` deleted
- [ ] Branch ready for merge: `feature/orchestrator-v2-m2-interpretation`
