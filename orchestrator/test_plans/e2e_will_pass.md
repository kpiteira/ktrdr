---
design: docs/architecture/autonomous-coding/DESIGN.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE.md
---

# Test Milestone: E2E Will Pass

**Branch:** Create new branch from sandbox default

A test milestone for validating E2E success flow. The calculator
module and tests are straightforward and should pass on first attempt.

---

## Task 1.1: Create calculator module

**File:** `calculator.py`
**Type:** CODING

**Description:**
Create a simple calculator module with add and subtract functions.

**Implementation Notes:**
- Function `add(a, b)` returns sum of two numbers
- Function `subtract(a, b)` returns difference of two numbers
- Use type hints for parameters and return values

**Acceptance Criteria:**
- [ ] add(a, b) returns a + b
- [ ] subtract(a, b) returns a - b
- [ ] Functions have type hints

---

## Task 1.2: Create calculator tests

**File:** `test_calculator.py`
**Type:** CODING

**Description:**
Create pytest tests for the calculator module.

**Implementation Notes:**
- Test add function with positive and negative numbers
- Test subtract function with positive and negative numbers
- Use simple assertions

**Acceptance Criteria:**
- [ ] Tests for add function exist
- [ ] Tests for subtract function exist
- [ ] All tests pass with pytest

---

## E2E Test

```bash
# Run calculator tests
cd /workspace
python -m pytest test_calculator.py -v

# Expected: All tests pass
# The output should show test_calculator.py::test_add PASSED
# and test_calculator.py::test_subtract PASSED
```
