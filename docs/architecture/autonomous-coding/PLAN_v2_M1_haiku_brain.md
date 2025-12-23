---
design: docs/architecture/autonomous-coding/DESIGN_v2_haiku_brain.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE_v2_haiku_brain.md
---

# Milestone 1: Haiku Brain + Plan Parsing

**Branch:** `feature/orchestrator-v2-m1-haiku-brain`
**Capability:** User can run orchestrator and have tasks extracted correctly, ignoring tasks inside code blocks

## Tasks

### Task 1.1: Create HaikuBrain class with extract_tasks()

**File:** `orchestrator/haiku_brain.py`
**Type:** CODING

**Description:**
Create the HaikuBrain class that uses Claude Code CLI to extract tasks from a milestone plan. The core capability is distinguishing real tasks from examples inside code blocks.

**Implementation Notes:**

- Reuse CLI invocation pattern from `llm_interpreter.py` (lines 184-200)
- Use prompt from architecture doc Appendix (Prompt 1: Extract Tasks)
- Return `list[ExtractedTask]` dataclass
- Parse JSON response, handle malformed JSON gracefully
- Include `find_claude_cli()` utility (move from llm_interpreter.py)

**Code sketch:**

```python
from dataclasses import dataclass
from typing import Literal
import json
import subprocess

@dataclass
class ExtractedTask:
    id: str
    title: str
    description: str

EXTRACT_TASKS_PROMPT = """You are parsing a milestone plan to extract tasks...
{plan_content}
"""

class HaikuBrain:
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.model = model

    def extract_tasks(self, plan_content: str) -> list[ExtractedTask]:
        prompt = EXTRACT_TASKS_PROMPT.format(plan_content=plan_content)
        response = self._invoke_haiku(prompt)
        return self._parse_tasks(response)

    def _invoke_haiku(self, prompt: str) -> str:
        claude_path = find_claude_cli()
        result = subprocess.run([
            claude_path, "--model", self.model, "--print",
            "--no-session-persistence", "--allowedTools", "", "-p", prompt
        ], capture_output=True, text=True, timeout=30)
        return result.stdout

    def _parse_tasks(self, response: str) -> list[ExtractedTask]:
        # Extract JSON from response, handle markdown wrapping
        data = json.loads(response)  # May need JSON extraction logic
        return [ExtractedTask(**t) for t in data]
```

**Tests:** `orchestrator/tests/test_haiku_brain.py`

- Test: Simple plan with 2 tasks → extracts both
- Test: Plan with tasks inside code blocks → ignores code block tasks
- Test: Plan with E2E example section → ignores example tasks
- Test: Empty plan → returns empty list
- Test: Malformed JSON response → raises clear error

**Acceptance Criteria:**

- [ ] `HaikuBrain.extract_tasks()` returns `list[ExtractedTask]`
- [ ] Tasks inside fenced code blocks are ignored
- [ ] Uses validated prompt from architecture doc
- [ ] Unit tests pass

---

### Task 1.2: Create test plan with tasks in code blocks

**File:** `orchestrator/test_plans/parsing_edge_case.md`
**Type:** CODING

**Description:**
Create a test plan file that has the edge case: real tasks AND example tasks inside code blocks. This is the exact bug that motivated v2.

**Content to create:**

```markdown
# Test Plan: Parsing Edge Case

This plan tests that the orchestrator correctly ignores tasks inside code blocks.

## Task 1.1: First Real Task

**Description:** This task should be extracted by the orchestrator.

**File:** `orchestrator/test_file_1.py`

**Acceptance Criteria:**

- [ ] This is a real task

---

## Task 1.2: Second Real Task

**Description:** This task should also be extracted.

**File:** `orchestrator/test_file_2.py`

**Acceptance Criteria:**

- [ ] This is also a real task

---

## E2E Test Scenario

Here's an example of what a milestone plan looks like:

` ` `markdown
## Task 2.1: Example Task Inside Code Block

**Description:** This task is inside a code block and should NOT be extracted.

## Task 2.2: Another Example Task

**Description:** Also inside code block, should be ignored.
` ` `

The orchestrator should find exactly 2 tasks (1.1 and 1.2), not 4.
```

(Note: The backticks in the code block example need to be actual backticks in the file)

**Acceptance Criteria:**

- [ ] File exists with 2 real tasks and 2 example tasks in code blocks
- [ ] Can be used for E2E testing of M1

---

### Task 1.3: Wire HaikuBrain to milestone_runner

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
Replace the `parse_plan()` call with `HaikuBrain.extract_tasks()`. The runner should read plan content and pass it to HaikuBrain.

**Implementation Notes:**

- Import HaikuBrain
- Read plan file content
- Call `brain.extract_tasks(content)`
- Convert `ExtractedTask` to existing `Task` model (add any missing fields as None)
- Keep `parse_e2e_scenario()` — move it from plan_parser.py first

**Code changes:**

```python
# Before:
from orchestrator.plan_parser import parse_plan

tasks = parse_plan(plan_path)

# After:
from orchestrator.haiku_brain import HaikuBrain
from pathlib import Path

brain = HaikuBrain()
plan_content = Path(plan_path).read_text()
extracted = brain.extract_tasks(plan_content)

# Convert to Task model for compatibility
tasks = [Task(
    id=t.id,
    title=t.title,
    description=t.description,
    file_path=None,  # /ktask reads this from plan
    acceptance_criteria=[],
    plan_file=str(plan_path),
    milestone_id=milestone_id,
) for t in extracted]
```

**Acceptance Criteria:**

- [ ] `run_milestone()` uses HaikuBrain instead of `parse_plan()`
- [ ] Task model compatibility maintained
- [ ] Existing tests still pass

---

### Task 1.4: Delete plan_parser.py

**File:** `orchestrator/plan_parser.py`
**Type:** CODING

**Description:**
Delete the regex-based plan parser. Keep only `parse_e2e_scenario()` — move it before deleting.

**Implementation Notes:**

- `parse_e2e_scenario()` is still needed (Decision 10: keep regex for E2E extraction)
- Move `parse_e2e_scenario()` to `orchestrator/milestone_runner.py` or create `orchestrator/utils.py`
- Delete rest of `plan_parser.py`
- Update imports across codebase
- Run `grep -r "from orchestrator.plan_parser" orchestrator/` to find all imports

**Acceptance Criteria:**

- [ ] `plan_parser.py` deleted
- [ ] `parse_e2e_scenario()` preserved and accessible
- [ ] All imports updated
- [ ] No broken imports: `uv run python -c "import orchestrator"`

---

### Task 1.5: M1 E2E Test

**Type:** VERIFICATION

**Description:**
Verify that the parsing edge case is handled correctly.

**Test Steps:**

```bash
# 1. Ensure clean environment
cd /Users/karl/Documents/dev/ktrdr2-spec-work

# 2. Run unit tests first
uv run pytest orchestrator/tests/test_haiku_brain.py -v

# 3. Test the edge case plan
# Option A: Add --dry-run flag to orchestrator (shows extracted tasks without running)
# Option B: Check task count programmatically

uv run python -c "
from orchestrator.haiku_brain import HaikuBrain
from pathlib import Path

brain = HaikuBrain()
content = Path('orchestrator/test_plans/parsing_edge_case.md').read_text()
tasks = brain.extract_tasks(content)

print(f'Found {len(tasks)} tasks:')
for t in tasks:
    print(f'  {t.id}: {t.title}')

assert len(tasks) == 2, f'Expected 2 tasks, got {len(tasks)}'
print('SUCCESS: Correctly extracted 2 tasks (ignored code block examples)')
"

# 4. Quality gates
make quality
```

**Success Criteria:**

- [ ] Edge case plan extracts exactly 2 tasks (not 4)
- [ ] Unit tests pass
- [ ] Quality gates pass
- [ ] No regressions in existing functionality

---

## Milestone 1 Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/test_haiku_brain.py`
- [ ] E2E test passes (Task 1.5)
- [ ] Quality gates pass: `make quality`
- [ ] `plan_parser.py` deleted (except `parse_e2e_scenario`)
- [ ] Branch ready for merge: `feature/orchestrator-v2-m1-haiku-brain`
