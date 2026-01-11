# E2E Test Failure Categories

When a test fails, categorize it to guide the main agent's response.

---

## Categories

### ENVIRONMENT

**Definition:** Failure due to infrastructure, not code or configuration.

**Examples:**
- Docker not running
- Service not responding after cure attempts
- Network connectivity issues
- Disk space issues

**Main Agent Action:** Ask human for help (can't fix via code)

**Report Format:**
```markdown
**Category:** ENVIRONMENT
**Diagnosis:** [Infrastructure issue description]
**Suggested Action:** Manual intervention required. [Specific steps]
```

---

### CONFIGURATION

**Definition:** Failure due to test parameters, strategy config, or data issues.

**Examples:**
- Zigzag threshold too high for asset type
- Wrong date range (no data)
- Strategy file missing
- Incorrect symbol/timeframe

**Main Agent Action:** Fix configuration, re-run test

**Report Format:**
```markdown
**Category:** CONFIGURATION
**Diagnosis:** [What's misconfigured and why it matters]
**Suggested Action:** [Specific configuration change needed]
```

---

### CODE_BUG

**Definition:** Failure due to bug in implementation code.

**Examples:**
- API returns error response
- Exception in service layer
- Wrong status returned
- Missing functionality

**Main Agent Action:** Fix code, re-run test

**Report Format:**
```markdown
**Category:** CODE_BUG
**Diagnosis:** [What code is broken and symptoms]
**Suggested Action:** [Where to look, what to fix]
**Evidence:** [Stack traces, error messages, logs]
```

---

### TEST_ISSUE

**Definition:** Failure due to problem with test recipe itself.

**Examples:**
- Test checks wrong endpoint
- Success criteria incorrect
- Test data outdated
- Sanity check threshold wrong

**Main Agent Action:** Fix test recipe, re-run test

**Report Format:**
```markdown
**Category:** TEST_ISSUE
**Diagnosis:** [What's wrong with the test]
**Suggested Action:** [How to fix the test recipe]
```

---

## Category Decision Tree

```
Test failed
    │
    ├─ Pre-flight failed after all cures?
    │       → ENVIRONMENT
    │
    ├─ Error mentions config/strategy/data?
    │       → CONFIGURATION
    │
    ├─ API error or exception in logs?
    │       → CODE_BUG
    │
    ├─ Test passed but sanity check failed?
    │       │
    │       ├─ Sanity check is about data quality?
    │       │       → CONFIGURATION
    │       │
    │       └─ Sanity check found impossible result?
    │               → CODE_BUG (or TEST_ISSUE if threshold wrong)
    │
    └─ Test expectations seem wrong?
            → TEST_ISSUE
```

---

## Common Failure Patterns

| Symptom | Likely Category | Why |
|---------|-----------------|-----|
| 100% accuracy | CONFIGURATION | Label imbalance (zigzag too high) |
| 0 trades in backtest | CONFIGURATION | Model only predicts HOLD |
| Strategy not found | CONFIGURATION | File path wrong or missing |
| Connection refused | ENVIRONMENT | Service not running |
| 500 error from API | CODE_BUG | Exception in handler |
| Wrong operation status | CODE_BUG | State machine bug |
| Test expects old API format | TEST_ISSUE | Test not updated |
