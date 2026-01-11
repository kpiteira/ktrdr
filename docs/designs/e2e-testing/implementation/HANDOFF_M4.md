# Handoff: Milestone 4 - Failure Handling & Sanity Checks

## Task 4.1 Complete: Failure Categories

**File:** `.claude/skills/e2e-testing/FAILURE_CATEGORIES.md`

### Four Categories

| Category | When to Use | Main Agent Action |
|----------|-------------|-------------------|
| ENVIRONMENT | Pre-flight fails after cures | Ask human |
| CONFIGURATION | Config/data issues, 100% accuracy | Fix config |
| CODE_BUG | API errors, exceptions | Fix code |
| TEST_ISSUE | Test expectations wrong | Fix test |

### Decision Tree

Key branch points:
1. Pre-flight exhausted → ENVIRONMENT
2. Error mentions config/strategy/data → CONFIGURATION
3. API error or exception → CODE_BUG
4. Sanity check fails on data quality → CONFIGURATION
5. Sanity check finds impossible result → CODE_BUG
6. Test expectations wrong → TEST_ISSUE

### For Task 4.2

Task 4.2 adds sanity check validation to the tester agent. The agent will use FAILURE_CATEGORIES.md to categorize failures when sanity checks fail (typically CONFIGURATION for 100% accuracy, CODE_BUG for impossible states).

---

## Task 4.2 Complete: Sanity Check Validation

**File:** `.claude/agents/e2e-tester.md`

### New Section Added

Added "Sanity Check Validation" section with:
- Why sanity checks matter (catches false positives)
- 4-step process (read, execute, compare, fail if any fail)
- Common checks table (accuracy, loss, duration, trade count)
- Reporting format with category and diagnosis

### Key Point

Sanity check failures are **real failures**, not warnings. The test FAILS and gets categorized (usually CONFIGURATION for data quality issues like 100% accuracy).

### For Task 4.3

Task 4.3 creates troubleshooting/training.md with known training issues from E2E_CHALLENGES_ANALYSIS.md. Focus on model collapse, 0 trades, NaN metrics, timeouts, and strategy file issues.
