---
design: docs/architecture/autonomous-coding/DESIGN_v2_haiku_brain.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE_v2_haiku_brain.md
---

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

```markdown
## Task 2.1: Example Task Inside Code Block

**Description:** This task is inside a code block and should NOT be extracted.

## Task 2.2: Another Example Task

**Description:** Also inside code block, should be ignored.
```

The orchestrator should find exactly 2 tasks (1.1 and 1.2), not 4.
