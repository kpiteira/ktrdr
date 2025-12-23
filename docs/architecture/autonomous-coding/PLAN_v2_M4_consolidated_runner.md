---
design: docs/architecture/autonomous-coding/DESIGN_v2_haiku_brain.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE_v2_haiku_brain.md
---

# Milestone 4: Consolidated Runner

**Branch:** `feature/orchestrator-v2-m4-consolidated`
**Builds on:** M3 (Retry/Escalate via Haiku)
**Capability:** Simpler codebase with all execution logic in one runner

## Tasks

### Task 4.1: Merge task execution into runner.py

**File:** `orchestrator/runner.py`
**Type:** CODING

**Description:**
Move task execution logic from `task_runner.py` into `runner.py`. The runner becomes the single coordination point.

**Implementation Notes:**

- Move `run_task()` function to runner.py
- Move `run_task_with_escalation()` function to runner.py
- Move `_build_prompt()` helper to runner.py
- Move `_estimate_tokens()` helper to runner.py
- Keep function signatures compatible for now
- Update imports within moved code

**Functions to move:**

```python
# From task_runner.py to runner.py:
async def run_task(...) -> TaskResult
async def run_task_with_escalation(...) -> TaskResult
def _build_prompt(task, plan_path, human_guidance) -> str
def _estimate_tokens(cost_usd) -> int
```

**Acceptance Criteria:**

- [ ] Task execution logic in runner.py
- [ ] Functions work the same as before
- [ ] No functionality changes, just reorganization

---

### Task 4.2: Merge E2E execution into runner.py

**File:** `orchestrator/runner.py`
**Type:** CODING

**Description:**
Move E2E execution from `e2e_runner.py` into `runner.py`.

**Implementation Notes:**

- `parse_e2e_scenario()` should already be accessible (from M1)
- Move `run_e2e_tests()` function to runner.py
- E2E uses same `brain.interpret_result()` for pass/fail detection
- Update the E2E flow to use HaikuBrain for interpretation

**Functions to move:**

```python
# From e2e_runner.py to runner.py:
async def run_e2e_tests(...) -> E2EResult
```

**Code changes for E2E interpretation:**

```python
# Before (if using regex):
if "PASSED" in output or "SUCCESS" in output:
    status = "passed"

# After (using HaikuBrain):
interpretation = brain.interpret_result(e2e_output)
if interpretation.status == "completed":
    status = "passed"
elif interpretation.status == "failed":
    status = "failed"
else:
    # needs_help - escalate for E2E issues
    status = "needs_help"
```

**Acceptance Criteria:**

- [ ] E2E execution logic in runner.py
- [ ] E2E result interpretation via HaikuBrain
- [ ] E2E flow integrated with task loop

---

### Task 4.3: Merge escalation into runner.py

**File:** `orchestrator/runner.py`
**Type:** CODING

**Description:**
Move escalation logic from `escalation.py` into runner.py.

**Implementation Notes:**

- Move `escalate_and_wait()` function to runner.py
- Move `EscalationInfo` dataclass to runner.py (or keep in models.py)
- Move `get_user_response()` helper to runner.py
- Simplify if possible — less indirection
- Keep notification integration (uses `notifications.py`)

**Functions to move:**

```python
# From escalation.py to runner.py:
async def escalate_and_wait(info, tracer, notify) -> str
def get_user_response(info) -> str
# EscalationInfo dataclass (or import from models.py)
```

**Acceptance Criteria:**

- [ ] Escalation logic in runner.py
- [ ] User notification still works (`notifications.py` unchanged)
- [ ] User input collection works
- [ ] Escalation flow integrates with task loop

---

### Task 4.4: Delete deprecated files

**Files to delete:**

- `orchestrator/task_runner.py`
- `orchestrator/e2e_runner.py`
- `orchestrator/escalation.py`

**Type:** CODING

**Description:**
Delete the files that have been merged into runner.py.

**Implementation Notes:**

- Ensure all functions have been moved to runner.py first
- Update all imports in other files
- Run `grep -r "from orchestrator.task_runner" orchestrator/` for each file
- Run `grep -r "from orchestrator.e2e_runner" orchestrator/`
- Run `grep -r "from orchestrator.escalation" orchestrator/`

**Files to check for imports:**

- `orchestrator/cli.py`
- `orchestrator/milestone_runner.py`
- `orchestrator/__init__.py`

**Acceptance Criteria:**

- [ ] `task_runner.py` deleted
- [ ] `e2e_runner.py` deleted
- [ ] `escalation.py` deleted
- [ ] All imports updated
- [ ] No broken imports

---

### Task 4.5: Update CLI imports

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Update CLI to import from consolidated runner.py instead of scattered modules.

**Implementation Notes:**

- Update imports at top of file
- `run_milestone()` should now be in runner.py or milestone_runner.py
- Verify all CLI commands still work
- Consider simplifying milestone_runner.py to just call runner.py

**CLI commands to verify:**

- `orchestrator run <plan>` — runs full milestone
- `orchestrator resume <plan>` — resumes from state
- `orchestrator task <plan> <task_id>` — runs single task
- `orchestrator history` — shows past runs
- `orchestrator costs` — shows cost summary
- `orchestrator health` — checks system status

**Acceptance Criteria:**

- [ ] All CLI imports updated
- [ ] No import errors: `uv run orchestrator --help`
- [ ] All commands functional

---

### Task 4.6: M4 E2E Test — Full Milestone

**Type:** VERIFICATION

**Description:**
Verify the full orchestrator works with consolidated codebase.

**Test Steps:**

```bash
# 1. Verify codebase is simpler
echo "=== File count before/after ==="
echo "Files in orchestrator/:"
ls orchestrator/*.py | wc -l
# Should be fewer than before (deleted: plan_parser, llm_interpreter,
# loop_detector, task_runner, e2e_runner, escalation = 6 files removed)

echo ""
echo "Remaining files:"
ls orchestrator/*.py

# 2. Verify all imports work
uv run python -c "
import orchestrator
from orchestrator.haiku_brain import HaikuBrain
from orchestrator.runner import run_milestone  # or wherever it ended up
from orchestrator.sandbox import SandboxManager
from orchestrator.state import OrchestratorState
from orchestrator.config import OrchestratorConfig
from orchestrator.notifications import send_notification
print('All imports successful')
"

# 3. Verify CLI commands work
uv run orchestrator --help
uv run orchestrator history
uv run orchestrator costs
uv run orchestrator health

# 4. Run unit tests
uv run pytest orchestrator/tests/ -v

# 5. Run full milestone (requires sandbox)
# This is the real E2E test
uv run orchestrator run orchestrator/test_plans/health_check.md

# Expected flow:
# 1. Tasks extracted correctly (M1 - HaikuBrain.extract_tasks)
# 2. Results interpreted semantically (M2 - HaikuBrain.interpret_result)
# 3. Failures get intelligent retry/escalate (M3 - HaikuBrain.should_retry_or_escalate)
# 4. Full milestone completes with consolidated runner (M4)

# 6. Quality gates
make quality
```

**Success Criteria:**

- [ ] Fewer orchestrator/*.py files than before
- [ ] All imports work
- [ ] All CLI commands functional
- [ ] Unit tests pass
- [ ] Full milestone can run to completion
- [ ] Quality gates pass

---

## Milestone 4 Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/`
- [ ] E2E test passes (Task 4.6)
- [ ] All previous milestone tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Deleted files:
  - [ ] `task_runner.py`
  - [ ] `e2e_runner.py`
  - [ ] `escalation.py`
- [ ] CLI commands all work
- [ ] Branch ready for merge: `feature/orchestrator-v2-m4-consolidated`

## Post-M4: Final Verification

After merging M4, run the complete regression check:

```bash
# Full test suite
uv run pytest orchestrator/tests/ -v

# All CLI commands
uv run orchestrator --help
uv run orchestrator run --help
uv run orchestrator resume --help
uv run orchestrator task --help
uv run orchestrator history
uv run orchestrator costs
uv run orchestrator health

# Full milestone E2E (with sandbox)
uv run orchestrator run orchestrator/test_plans/health_check.md --notify

# Verify the parsing edge case is still fixed
uv run python -c "
from orchestrator.haiku_brain import HaikuBrain
from pathlib import Path

brain = HaikuBrain()
content = Path('orchestrator/test_plans/parsing_edge_case.md').read_text()
tasks = brain.extract_tasks(content)
assert len(tasks) == 2, f'Regression: Expected 2 tasks, got {len(tasks)}'
print('Parsing edge case still works correctly')
"

# Quality gates
make quality

echo "=== v2 Haiku Brain Implementation Complete ==="
```
