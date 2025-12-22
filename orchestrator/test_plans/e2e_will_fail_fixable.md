---
design: docs/architecture/autonomous-coding/DESIGN.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE.md
---

# Test Milestone: E2E Will Fail (Fixable)

**Branch:** Create new branch from sandbox default

A test milestone for validating E2E failure and fix flow. The greeting
module intentionally contains a bug that Claude should diagnose and fix.

---

## Task 1.1: Create greeting module

**File:** `greeting.py`
**Type:** CODING

**Description:**
Create a greeting function that returns "Hello, {name}!"

NOTE: This task intentionally introduces a bug to test the E2E fix flow.
When implementing, "accidentally" write the greeting without the comma:
`return f"Hello {name}!"` instead of `return f"Hello, {name}!"`

The E2E test will fail, and Claude should be able to diagnose the
missing comma and suggest a fix.

**Implementation Notes:**
When implementing, create the file with this intentional bug:
```python
def greet(name: str) -> str:
    return f"Hello {name}!"  # Bug: missing comma after Hello
```

**Acceptance Criteria:**
- [ ] greet(name) function exists
- [ ] Function returns greeting string

---

## E2E Test

```bash
# Test greeting function
cd /workspace
python -c "from greeting import greet; assert greet('World') == 'Hello, World!', f'Got: {greet(\"World\")}'"

# Expected: Should fail initially due to missing comma in output
# The assertion will fail because greet('World') returns "Hello World!"
# instead of "Hello, World!" (missing comma)
#
# Claude should diagnose this as:
#   DIAGNOSIS: The greeting function is missing a comma after "Hello"
#   FIXABLE: yes
#   FIX_PLAN: Change 'return f"Hello {name}!"' to 'return f"Hello, {name}!"'
```
