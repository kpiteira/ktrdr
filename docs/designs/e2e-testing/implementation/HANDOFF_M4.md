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

---

## Task 4.3 Complete: Training Troubleshooting Module

**File:** `.claude/skills/e2e-testing/troubleshooting/training.md`

### Issues Documented

| Issue | Category | Key Symptom |
|-------|----------|-------------|
| Model Collapse | CONFIGURATION | 100% accuracy |
| 0 Trades | CONFIGURATION | Trade count = 0 |
| NaN Metrics | CODE_BUG/CONFIG | Loss/accuracy is NaN |
| Training Timeout | ENVIRONMENT | Status stuck on "running" |
| Strategy Not Found | CONFIGURATION | Immediate failure |

### Pattern

Each issue follows the structure:
- Symptom (what you see)
- Cause (why it happens)
- Diagnosis Steps (executable bash commands)
- Solution (specific fixes)
- Prevention (where applicable)

### For Task 4.4

Task 4.4 adds explicit failure categorization guidance to the tester agent with a quick reference table and example report format.

---

## Task 4.4 Complete: Failure Categorization Guidance

**File:** `.claude/agents/e2e-tester.md`

### Changes Made

Replaced "Failure Categories" section with expanded "Failure Categorization":
- Statement that categorization is MANDATORY
- Link to FAILURE_CATEGORIES.md for full decision tree
- Quick reference table (6 failure types → categories)
- Full example report showing proper format

### Key Point

The agent MUST assign a category to every failure. The example shows the complete format including Category, Failure Point, Evidence, Diagnosis, and Suggested Action.
