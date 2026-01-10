---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Failure Handling & Sanity Checks

**Goal:** Add failure categorization and enhanced sanity checks so test failures are actionable for the main agent.

**Branch:** `feature/e2e-framework-m4`

**Builds On:** M3 (Pre-Flight Cure System)

---

## E2E Test Scenario

**Purpose:** Verify sanity checks catch false positives and failures are properly categorized.

**Duration:** ~2 minutes

**Prerequisites:**
- M3 complete (cure system works)
- Docker running

**Test Steps:**

```markdown
1. Create a test scenario that triggers 100% accuracy (model collapse)
   - Use EURUSD with 2.5% zigzag threshold (all HOLD labels)
2. Invoke e2e-tester with "Run tests: training/smoke"
3. Training completes "successfully" (100% accuracy)
4. Sanity check catches: accuracy >= 99% threshold
5. Tester reports ❌ FAILED with category=CONFIGURATION
6. Diagnosis points to label distribution issue
```

**Success Criteria:**
- [ ] Sanity check triggers on 100% accuracy
- [ ] Failure category is CONFIGURATION (not CODE_BUG)
- [ ] Diagnosis mentions label distribution
- [ ] Suggested action is clear

---

## Task 4.1: Define Failure Categories

**File:** `.claude/skills/e2e-testing/FAILURE_CATEGORIES.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create a reference document defining the four failure categories and how to determine which applies.

**What to create:**

```markdown
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
```

**Acceptance Criteria:**
- [ ] All four categories defined
- [ ] Decision tree is clear
- [ ] Common patterns documented
- [ ] Report format specified for each

---

## Task 4.2: Add Sanity Check Validation to Tester Agent

**File:** `.claude/agents/e2e-tester.md`

**Type:** CODING

**Task Categories:** State Machine, Cross-Component

**Description:**
Update the tester agent to emphasize sanity check validation and proper failure categorization.

**Add new section:**

```markdown
## Sanity Check Validation

### Why Sanity Checks Matter

From E2E_CHALLENGES_ANALYSIS.md: A test can "pass" all steps but still be invalid.

**Example:** Training completes, returns "success", metrics look normal... but accuracy is 100%, indicating model collapse. The model learned to always predict HOLD because training data had no BUY/SELL labels.

### Sanity Check Process

After all test steps pass:

1. **Read sanity checks from test recipe**
2. **Execute each check command**
3. **Compare against thresholds**
4. **If ANY sanity check fails:**
   - The test FAILS (not a warning!)
   - Categorize using FAILURE_CATEGORIES.md
   - Include sanity check details in report

### Common Sanity Checks

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Accuracy < 99% | >= 99% fails | Model collapse |
| Loss > 0.001 | <= 0.001 fails | Trivial solution |
| Duration > 1s | <= 1s fails | Skipped execution |
| Trade count > 0 | == 0 fails | No signals generated |

### Sanity Check Reporting

```markdown
**Sanity Checks:**
- Accuracy: 100% ❌ (threshold: < 99%)
- Loss: 0.0001 ❌ (threshold: > 0.001)

**Category:** CONFIGURATION
**Diagnosis:** Model collapse detected. 100% accuracy with near-zero loss indicates training data has no class variance. Likely cause: zigzag threshold too high for this asset type.
**Suggested Action:** Check label distribution. For forex (EURUSD), use 0.5% zigzag threshold instead of 2.5%.
```
```

**Acceptance Criteria:**
- [ ] Sanity check process documented
- [ ] Common checks with thresholds listed
- [ ] Reporting format specified
- [ ] Connection to failure categories clear

---

## Task 4.3: Create troubleshooting/training.md

**File:** `.claude/skills/e2e-testing/troubleshooting/training.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the training-specific troubleshooting module with known issues from E2E_CHALLENGES_ANALYSIS.md.

**What to create:**

```markdown
# Troubleshooting: Training

Common training test failures and their solutions.

---

## Model Collapse (100% Accuracy)

**Symptom:**
- Training completes "successfully"
- Accuracy is 100% or very high (>99%)
- Loss is very low (<0.001)
- Model predicts same class for all inputs

**Cause:** Class imbalance in training data. Typically because:
- Zigzag threshold too high for asset volatility
- Date range has no significant price movements
- Wrong labeling configuration

**Diagnosis Steps:**
```bash
# Check what the model predicts
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '.data.result_summary.training_metrics'

# If accuracy is 100%, check label distribution
# (Requires checking training logs or re-running with verbose)
```

**Solution:**
1. For forex (EURUSD, GBPUSD, etc.): Use 0.5% zigzag, not 2.5%
2. For stocks: 2.5% zigzag is usually fine
3. Extend date range to capture more price movement

**Prevention:**
- Always check label distribution before training
- Sanity check: accuracy < 99%

---

## 0 Trades in Backtest

**Symptom:**
- Backtest completes
- Trade count is 0
- All predictions are HOLD

**Cause:** Model collapse (see above) caused model to never predict BUY/SELL.

**Diagnosis Steps:**
```bash
# Check backtest results
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '.data.result_summary.trade_count'
```

**Solution:** Fix the underlying model collapse issue, retrain.

---

## NaN in Training Metrics

**Symptom:**
- Training metrics show NaN values
- Loss is NaN
- Accuracy is NaN or 0

**Cause:** Usually numerical instability:
- Learning rate too high
- Data has NaN values
- Normalization issue

**Diagnosis Steps:**
```bash
# Check for NaN in data
docker compose logs backend --since 5m | grep -i "nan\|inf"
```

**Solution:**
1. Check data for NaN values
2. Try lower learning rate
3. Check normalization in strategy config

---

## Training Timeout

**Symptom:**
- Training doesn't complete within expected time
- Status stays "running" indefinitely

**Cause:**
- Dataset too large
- Worker overwhelmed
- Deadlock in training loop

**Diagnosis Steps:**
```bash
# Check training progress
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | jq '.data.progress'

# Check worker health
curl -s http://localhost:5002/health

# Check for errors
docker compose logs backend --since 10m | grep -i "error\|timeout"
```

**Solution:**
1. Cancel stuck operation: `DELETE /api/v1/operations/$TASK_ID`
2. Use smaller dataset for testing
3. Restart training worker if stuck

---

## Strategy File Not Found

**Symptom:**
- Training fails immediately
- Error: "Strategy file not found: {name}.yaml"

**Cause:** Strategy file not in expected location.

**Diagnosis Steps:**
```bash
# Check strategy exists
ls ~/.ktrdr/shared/strategies/{strategy_name}.yaml

# Check mounted in Docker
docker compose exec backend ls /app/strategies/
```

**Solution:**
1. Copy strategy to `~/.ktrdr/shared/strategies/`
2. Verify Docker volume mount is correct
```

**Acceptance Criteria:**
- [ ] All known training issues documented
- [ ] Diagnosis steps are executable
- [ ] Solutions are specific
- [ ] Prevention tips included

---

## Task 4.4: Update Tester Agent with Category Assignment

**File:** `.claude/agents/e2e-tester.md`

**Type:** CODING

**Task Categories:** State Machine

**Description:**
Add explicit guidance on how to assign failure categories based on symptoms.

**Add to agent definition:**

```markdown
## Failure Categorization

When a test fails, you MUST assign a category. Use [FAILURE_CATEGORIES.md](../skills/e2e-testing/FAILURE_CATEGORIES.md).

### Quick Reference

| Failure Type | Category | Key Indicator |
|--------------|----------|---------------|
| Pre-flight fails after cures | ENVIRONMENT | Infrastructure broken |
| Config/strategy/data error | CONFIGURATION | Error message mentions config |
| API error or exception | CODE_BUG | 500 error, stack trace |
| Sanity check fails (data quality) | CONFIGURATION | 100% accuracy, 0 trades |
| Sanity check fails (impossible) | CODE_BUG | Negative time, impossible state |
| Test expectations outdated | TEST_ISSUE | Test checks wrong thing |

### Categorization in Report

Always include category prominently:

```markdown
### training/smoke: ❌ FAILED

**Category:** CONFIGURATION

**Pre-flight:** PASSED
**Failure Point:** Sanity check

**Expected:** Accuracy < 99%
**Actual:** Accuracy = 100%

**Evidence:**
- Training metrics: {"accuracy": 1.0, "loss": 0.0003}
- All predictions: HOLD

**Diagnosis:** Model collapse due to label imbalance. EURUSD with 2.5% zigzag threshold produces 100% HOLD labels.

**Suggested Action:**
1. Change zigzag threshold to 0.5% for forex
2. Verify label distribution before training
3. Re-run test
```
```

**Acceptance Criteria:**
- [ ] Quick reference table added
- [ ] Categorization is mandatory
- [ ] Example shows full format
- [ ] Links to FAILURE_CATEGORIES.md

---

## Milestone 4 Completion Checklist

### All Tasks Complete
- [ ] Task 4.1: FAILURE_CATEGORIES.md created
- [ ] Task 4.2: Tester agent updated for sanity checks
- [ ] Task 4.3: troubleshooting/training.md created
- [ ] Task 4.4: Tester agent updated for categorization

### E2E Verification
- [ ] Test with 100% accuracy → CONFIGURATION category
- [ ] Test with API error → CODE_BUG category
- [ ] Pre-flight exhausted → ENVIRONMENT category
- [ ] Sanity checks are enforced (not warnings)

### Quality Gates
- [ ] `make quality` passes
- [ ] All files committed to feature branch
- [ ] Failure categories match VALIDATION.md decisions
