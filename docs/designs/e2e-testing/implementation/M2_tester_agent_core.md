---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Tester Agent Core

**Goal:** Create the e2e-tester agent that can execute tests from the skill and return structured PASS/FAIL reports.

**Branch:** `feature/e2e-framework-m2`

**Builds On:** M1 (Skill Foundation)

---

## E2E Test Scenario

**Purpose:** Verify tester agent executes a test and returns a proper report.

**Duration:** ~1 minute

**Prerequisites:**
- M1 complete (skill and training/smoke test exist)
- Docker running with backend healthy

**Test Steps:**

```markdown
1. Invoke e2e-tester agent with: "Run tests: training/smoke"
2. Agent loads e2e-testing skill
3. Agent finds and loads training/smoke.md
4. Agent runs pre-flight checks
5. Agent executes test steps
6. Agent validates success criteria
7. Agent returns structured report
```

**Success Criteria:**
- [ ] Agent loads skill correctly
- [ ] Agent finds training/smoke test
- [ ] Pre-flight checks run
- [ ] Test executes without agent errors
- [ ] Report follows expected format (PASSED/FAILED with evidence)

---

## Task 2.1: Create e2e-tester Agent Definition

**File:** `.claude/agents/e2e-tester.md`

**Type:** CODING

**Task Categories:** Configuration, Wiring/DI

**Description:**
Create the e2e-tester agent definition following Claude Code agent conventions. This agent executes tests and returns structured reports. It does NOT design tests (that's the designer agent in M5).

**What to create:**

```markdown
---
name: e2e-tester
description: Use this agent to execute E2E tests and get detailed PASS/FAIL reports. Invoke after milestone implementation to validate the feature works. The agent runs pre-flight checks, executes test steps, and reports results with evidence.
tools: Bash, Read, Grep, Write, Glob
model: sonnet
color: green
---

# E2E Test Executor

## Role

You execute E2E tests from the e2e-testing skill and return structured reports. You are invoked by the main coding agent after implementing a milestone to validate the implementation works.

**You DO:**
- Load test recipes from the e2e-testing skill
- Run pre-flight checks before each test
- Execute test steps exactly as documented
- Validate success criteria
- Report PASS/FAIL with evidence

**You DO NOT:**
- Design new tests (that's e2e-test-designer)
- Modify code to fix failures (report back to main agent)
- Skip pre-flight checks
- Make up test steps not in the recipe

---

## Input Format

You receive a test execution request:

```markdown
## E2E Test Execution Request

**Tests to Run:**
1. training/smoke
2. [additional tests]

**Context:** [Optional: what was implemented, why these tests]
```

---

## Process

### 1. Load the Skill

Read `.claude/skills/e2e-testing/SKILL.md` to understand available tests.

### 2. For Each Test

#### a. Load Test Recipe

Read the test file (e.g., `.claude/skills/e2e-testing/tests/training/smoke.md`)

#### b. Run Pre-Flight Checks

1. Load required pre-flight modules (e.g., `preflight/common.md`)
2. Execute each check
3. If any check fails:
   - Note the failure
   - (M3+) Apply cure if available
   - (M3+) Retry check
   - If still failing, stop and report pre-flight failure

#### c. Execute Test Steps

1. Run each step's command
2. Capture output
3. Compare against expected results
4. If step fails, note but continue to gather full picture

#### d. Validate Success Criteria

Check each criterion against actual results.

#### e. Run Sanity Checks

**CRITICAL:** Sanity checks catch false positives.
- 100% accuracy = likely model collapse
- Instant completion = likely cached/skipped

### 3. Compile Report

Generate structured report (see Output Format).

---

## Output Format

```markdown
## E2E Test Results

### Summary

| Test | Result | Duration |
|------|--------|----------|
| training/smoke | ✅ PASSED | 8s |

---

### training/smoke: ✅ PASSED

**Pre-flight:** All checks passed
**Execution:** Completed successfully

**Evidence:**
- Operation ID: `op_training_20260110_...`
- Status: completed
- Samples: 258
- Training time: 2.1s

**Sanity Checks:**
- Accuracy: 87% (< 99% threshold) ✅
- Loss: 0.34 (> 0.001 threshold) ✅

---

### [test-name]: ❌ FAILED

**Pre-flight:** PASSED | FAILED (details)
**Failure Point:** [Which step failed]

**Expected:** [What should have happened]
**Actual:** [What actually happened]

**Evidence:**
- [Concrete data: IDs, responses, logs]

**Diagnosis:** [Your assessment]
**Suggested Action:** [What main agent should do]
```

---

## Key Behaviors

### Evidence Collection

Always capture:
- Operation IDs
- API response bodies (key fields)
- Relevant log excerpts
- Timing information

### Failure Reporting

Be specific:
- BAD: "Test failed"
- GOOD: "Expected status 'completed' but got 'failed'. Error in logs: 'Strategy file not found: test.yaml' at line 42 of backend logs."

### Sanity Check Failures

Sanity check failures are real failures:
- BAD: "Test passed (but accuracy was 100%)"
- GOOD: "❌ FAILED - Sanity check: Accuracy 100% exceeds 99% threshold, indicating model collapse"

---

## Example Session

**Input:**
```
Run tests: training/smoke
```

**Process:**
1. Load `.claude/skills/e2e-testing/SKILL.md`
2. Find training/smoke in catalog
3. Load `.claude/skills/e2e-testing/tests/training/smoke.md`
4. Load `.claude/skills/e2e-testing/preflight/common.md`
5. Run pre-flight: Docker ✅, API ✅, Sandbox ✅
6. Execute step 1: Start training → task_id received
7. Execute step 2: Wait → status=completed, samples=258
8. Execute step 3: Check logs → no errors
9. Validate criteria: all pass
10. Run sanity checks: accuracy=87% ✅, loss=0.34 ✅
11. Generate report

**Output:**
```
## E2E Test Results

### Summary
| Test | Result | Duration |
|------|--------|----------|
| training/smoke | ✅ PASSED | 12s |

### training/smoke: ✅ PASSED
...
```
```

**Implementation Notes:**
- Model: sonnet (needs reasoning for test execution)
- Tools: Bash for commands, Read for files, Grep for logs
- Follow integration-test-specialist.md pattern for structure

**Testing Requirements:**

*Integration Test:*
- Invoke agent with "Run tests: training/smoke"
- Verify report is returned in correct format

**Acceptance Criteria:**
- [ ] Agent definition follows Claude Code conventions
- [ ] Input/output formats match VALIDATION.md contracts
- [ ] Process steps are clear and complete
- [ ] Sanity checks emphasized as real failures

---

## Task 2.2: Create Test Execution Helpers

**File:** `.claude/skills/e2e-testing/helpers/run-test.sh`

**Type:** CODING

**Task Categories:** Background/Async

**Description:**
Create a helper script that the tester agent can use to run pre-flight checks and capture structured output. This reduces the number of individual bash commands the agent needs to run.

**What to create:**

```bash
#!/bin/bash
# run-test.sh - Helper for e2e-tester agent
# Usage: ./run-test.sh preflight|execute <test-path>

set -e

# Load sandbox config if present
[ -f .env.sandbox ] && source .env.sandbox
export API_PORT=${KTRDR_API_PORT:-8000}

case "$1" in
  preflight)
    # Run pre-flight checks, output JSON
    echo '{"check": "docker", "status": "checking"}'
    UNHEALTHY=$(docker compose ps --format "table {{.State}}" 2>/dev/null | grep -v "STATE" | grep -v "running" | wc -l | tr -d ' ' || echo "999")
    if [ "$UNHEALTHY" -gt 0 ]; then
      echo '{"check": "docker", "status": "FAILED", "message": "Containers not running"}'
      exit 1
    fi
    echo '{"check": "docker", "status": "PASSED"}'

    echo '{"check": "api", "status": "checking"}'
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$API_PORT/api/v1/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" != "200" ]; then
      echo '{"check": "api", "status": "FAILED", "message": "Backend not responding (HTTP '$HTTP_CODE')"}'
      exit 1
    fi
    echo '{"check": "api", "status": "PASSED"}'

    echo '{"preflight": "PASSED", "api_port": "'$API_PORT'"}'
    ;;

  *)
    echo "Usage: $0 preflight"
    exit 1
    ;;
esac
```

**Implementation Notes:**
- JSON output for easy parsing
- Sandbox-aware
- Can be extended for more check types

**Acceptance Criteria:**
- [ ] Script is executable
- [ ] Outputs valid JSON
- [ ] Handles sandbox detection
- [ ] Exit codes reflect pass/fail

---

## Task 2.3: Update SKILL.md with Agent Reference

**File:** `.claude/skills/e2e-testing/SKILL.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update SKILL.md to reference the tester agent and explain how the skill is used.

**Changes to add:**

```markdown
## Agents That Use This Skill

| Agent | Purpose | When Invoked |
|-------|---------|--------------|
| [e2e-tester](../../agents/e2e-tester.md) | Execute tests, report results | After milestone implementation |
| e2e-test-designer | Find/propose tests | During /kdesign-impl-plan (M5) |

## How Tests Are Executed

The e2e-tester agent:
1. Loads this skill (SKILL.md)
2. Finds requested tests in the catalog
3. Loads test recipe files
4. Runs pre-flight checks
5. Executes test steps
6. Reports PASS/FAIL with evidence

See [e2e-tester agent](../../agents/e2e-tester.md) for full details.
```

**Acceptance Criteria:**
- [ ] Agent reference added
- [ ] Execution flow explained
- [ ] Links are correct

---

## Task 2.4: Verify Agent Works End-to-End

**File:** N/A (verification task)

**Type:** MIXED

**Task Categories:** Cross-Component

**Description:**
Manually verify the tester agent works by invoking it and checking the output matches expected format.

**Verification Steps:**

1. Start Docker environment:
   ```bash
   docker compose up -d
   ```

2. Invoke tester agent (via main Claude session):
   ```
   Use the e2e-tester agent to run: training/smoke
   ```

3. Verify output:
   - [ ] Agent loads skill correctly
   - [ ] Agent finds training/smoke test
   - [ ] Pre-flight checks run and pass
   - [ ] Test executes
   - [ ] Report has correct format
   - [ ] Evidence is captured

4. If test fails (expected in some cases):
   - [ ] Failure is reported with details
   - [ ] Diagnosis provided
   - [ ] Suggested action given

**Acceptance Criteria:**
- [ ] Agent invocation works
- [ ] Report format matches specification
- [ ] Evidence is captured correctly

---

## Milestone 2 Completion Checklist

### All Tasks Complete
- [ ] Task 2.1: e2e-tester agent definition
- [ ] Task 2.2: Test execution helper script
- [ ] Task 2.3: SKILL.md updated with agent reference
- [ ] Task 2.4: End-to-end verification

### E2E Verification
- [ ] Invoke tester with "Run tests: training/smoke"
- [ ] Tester loads skill and finds test
- [ ] Pre-flight checks execute
- [ ] Test steps execute
- [ ] Report returned in correct format
- [ ] Evidence captured (operation ID, metrics)

### Quality Gates
- [ ] `make quality` passes
- [ ] Agent definition follows conventions
- [ ] All files committed to feature branch
