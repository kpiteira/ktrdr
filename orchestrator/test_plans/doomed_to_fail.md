# Test Milestone: Doomed to Fail

This test plan is designed to trigger loop detection by presenting an
impossible task that will fail repeatedly with similar errors.

---

## Task 1.1: Impossible task

**File:** `orchestrator/impossible.py`
**Type:** CODING

**Description:**
Create a file that simultaneously satisfies all of the following requirements:

1. Has exactly 100 lines
2. Has exactly 50 lines
3. Contains no newline characters

(Note: This is intentionally impossible to satisfy all criteria simultaneously.
The contradictory line count requirements cannot be met, and a file with
multiple lines cannot avoid newline characters. Claude should fail repeatedly
with similar errors, triggering loop detection after 3 attempts.)

**Acceptance Criteria:**
- [ ] File has exactly 100 lines
- [ ] File has exactly 50 lines
- [ ] File contains no newline characters
