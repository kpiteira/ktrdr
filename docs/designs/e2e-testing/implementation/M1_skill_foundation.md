---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Skill Foundation

**Goal:** Create the e2e-testing skill structure with one complete test recipe (training/smoke) that Claude can navigate and use.

**Branch:** `feature/e2e-framework-m1`

**Builds On:** Nothing (foundation)

---

## E2E Test Scenario

**Purpose:** Verify Claude can load the skill and navigate to a specific test recipe.

**Duration:** Manual verification (~2 minutes)

**Test Steps:**

```markdown
1. Load the e2e-testing skill
2. Find the training/smoke test in the catalog
3. Navigate to the test recipe file
4. Confirm all sections are present (pre-flight, execution, validation)
```

**Success Criteria:**
- [ ] SKILL.md loads without errors
- [ ] Catalog shows training/smoke test
- [ ] Link to tests/training/smoke.md works
- [ ] Test recipe has all required sections

---

## Task 1.1: Create Skill Directory Structure

**File(s):** `.claude/skills/e2e-testing/` (directory)

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the skill directory structure following Claude Code conventions. This establishes the skeleton that all other tasks will populate.

**What to create:**
```
.claude/skills/e2e-testing/
├── SKILL.md              # Entry point (Task 1.2)
├── TEMPLATE.md           # Test template (Task 1.3)
├── tests/
│   └── training/
│       └── smoke.md      # First test (Task 1.4)
├── preflight/
│   └── common.md         # Common checks (Task 1.5)
├── patterns/             # Empty for now
└── troubleshooting/      # Empty for now
```

**Implementation Notes:**
- Use `mkdir -p` to create nested directories
- Create placeholder `.gitkeep` in empty directories (patterns/, troubleshooting/)

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify structure exists
ls -la .claude/skills/e2e-testing/
ls -la .claude/skills/e2e-testing/tests/training/
ls -la .claude/skills/e2e-testing/preflight/
```

**Acceptance Criteria:**
- [ ] All directories exist
- [ ] No extraneous files

---

## Task 1.2: Create SKILL.md Entry Point

**File:** `.claude/skills/e2e-testing/SKILL.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the skill entry point with catalog and navigation. Must be under 500 lines for progressive disclosure. Links to supporting files use markdown format so Claude loads them on-demand.

**What to create:**

```markdown
---
name: e2e-testing
description: Knowledge base for E2E test design and execution. Used by e2e-test-designer (planning) and e2e-tester (execution) agents.
---

# E2E Testing Skill

## Purpose

Knowledge base for E2E test design and execution. Used by:
- **e2e-test-designer** agent — Find/propose tests during planning
- **e2e-tester** agent — Execute tests and report results

## Test Catalog

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [training/smoke](tests/training/smoke.md) | Training | <30s | Any training changes |

## Pre-Flight Modules

| Module | Checks | Used By |
|--------|--------|---------|
| [common](preflight/common.md) | Docker, sandbox, API health | All tests |

## Reusable Patterns

*(To be added in later milestones)*

## Troubleshooting

*(To be added in later milestones)*

## Creating New Tests

Use [TEMPLATE.md](TEMPLATE.md) when creating new test recipes.
```

**Implementation Notes:**
- Follow existing skill patterns (see distributed-workers/SKILL.md)
- Catalog will grow as tests are added
- Links use relative paths for portability

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify file exists and has correct frontmatter
head -10 .claude/skills/e2e-testing/SKILL.md
```

**Acceptance Criteria:**
- [ ] SKILL.md exists with correct frontmatter
- [ ] Under 500 lines (currently ~30)
- [ ] Links use correct relative paths
- [ ] Catalog shows training/smoke test

---

## Task 1.3: Create TEMPLATE.md

**File:** `.claude/skills/e2e-testing/TEMPLATE.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the template for new test recipes. This enforces consistency and ensures all tests have required sections (pre-flight, execution, validation, sanity checks).

**Template structure:**

```markdown
# Test: {category}/{name}

**Purpose:** [One sentence describing what this test validates]
**Duration:** [Expected time]
**Category:** [Training | Backtest | Data | Integration]

---

## Pre-Flight Checks

**Required modules:**
- [common](../preflight/common.md)
- [Add domain-specific if needed]

**Test-specific checks:**
- [ ] [Any checks unique to this test]

---

## Test Data

```json
{
  // Request payload
}
```

**Why this data:** [Explain parameter choices]

---

## Execution Steps

### 1. [Step Name]

**Command:**
```bash
# Command to execute
```

**Expected:**
- [What should happen]

### 2. [Next Step]
...

---

## Success Criteria

- [ ] [Observable outcome 1]
- [ ] [Observable outcome 2]

---

## Sanity Checks

**CRITICAL:** These catch false positives (e.g., 100% accuracy = model collapse)

- [ ] [Sanity check 1 with threshold]
- [ ] [Sanity check 2]

---

## Troubleshooting

**If [symptom]:**
- **Cause:** [Why this happens]
- **Cure:** [How to fix]

---

## Evidence to Capture

- Operation ID: `{operation_id}`
- Logs: `docker compose logs backend --since 5m | grep {pattern}`
- Response: [Key fields to save]
```

**Implementation Notes:**
- Sanity checks section is REQUIRED (from validation decision)
- Each test owns its sanity checks (recipe-owned, not centralized)
- Troubleshooting section captures test-specific gotchas

**Acceptance Criteria:**
- [ ] Template has all required sections
- [ ] Sanity checks section is prominent
- [ ] Instructions are clear for Claude

---

## Task 1.4: Create training/smoke.md Test Recipe

**File:** `.claude/skills/e2e-testing/tests/training/smoke.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the first real test recipe by migrating content from SCENARIOS.md scenario 1.1 (Local Training - Smoke Test). This proves the template works and provides immediate value.

**Source:** `docs/testing/SCENARIOS.md` lines 63-136 (scenario 1.1)

**What to create:**

```markdown
# Test: training/smoke

**Purpose:** Quick validation that training starts, completes, and produces valid output
**Duration:** <30 seconds
**Category:** Training

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Strategy file exists: `~/.ktrdr/shared/strategies/test_e2e_local_pull.yaml`
- [ ] Data available: EURUSD 1d has data in cache

---

## Test Data

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "strategy_name": "test_e2e_local_pull",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

**Why this data:**
- EURUSD 1d: 258 samples, trains in ~2s (fast feedback)
- 1 year range: Sufficient for smoke test, not too large
- test_e2e_local_pull: Known-good strategy for testing

---

## Execution Steps

### 1. Start Training

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `success: true`
- `status: "training_started"`
- `task_id` returned

### 2. Wait for Completion

**Command:**
```bash
sleep 10
curl -s "http://localhost:${API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, samples:.data.result_summary.data_summary.total_samples}'
```

**Expected:**
- `status: "completed"`
- `samples: 258`

### 3. Verify No Errors

**Command:**
```bash
docker compose logs backend --since 2m | grep -i "error\|exception" | grep -v "No error"
```

**Expected:**
- No error lines (or only benign ones)

---

## Success Criteria

- [ ] Training starts successfully (HTTP 200, task_id returned)
- [ ] Training completes (status = "completed")
- [ ] Correct sample count (258 samples)
- [ ] No errors in logs

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Accuracy < 99%** — If accuracy is 100%, likely model collapse (see E2E_CHALLENGES_ANALYSIS.md)
- [ ] **Loss > 0.001** — If loss is ~0, training may have collapsed to trivial solution
- [ ] **Duration > 1s** — If instant, something is wrong (cached result? skipped training?)

**Check command:**
```bash
curl -s "http://localhost:${API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '.data.result_summary.training_metrics | {accuracy, final_loss, training_time}'
```

---

## Troubleshooting

**If "strategy file not found":**
- **Cause:** Strategy not in shared directory
- **Cure:** Copy strategy to `~/.ktrdr/shared/strategies/`

**If training times out:**
- **Cause:** Backend may be overloaded or stuck
- **Cure:** Check `docker compose logs backend --tail 50`

**If 0 samples:**
- **Cause:** Data not in cache
- **Cure:** Load data first: `curl -X POST .../api/v1/data/EURUSD/1d`

---

## Evidence to Capture

- Operation ID: `$TASK_ID`
- Final status: `curl ... | jq '.data.status'`
- Training metrics: `curl ... | jq '.data.result_summary.training_metrics'`
- Logs: `docker compose logs backend --since 5m | grep $TASK_ID`
```

**Implementation Notes:**
- Uses `${API_PORT:-8000}` for sandbox compatibility
- Sanity checks from E2E_CHALLENGES_ANALYSIS.md lessons
- Troubleshooting covers known gotchas

**Testing Requirements:**

*Integration Test:*
- Manually execute the test steps to verify they work

**Acceptance Criteria:**
- [ ] Test recipe follows TEMPLATE.md structure
- [ ] All commands are executable
- [ ] Sanity checks have specific thresholds
- [ ] Troubleshooting covers known issues

---

## Task 1.5: Create preflight/common.md

**File:** `.claude/skills/e2e-testing/preflight/common.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the common pre-flight module with checks that ALL tests need. This milestone creates checks WITHOUT cures (cures added in M3).

**What to create:**

```markdown
# Pre-Flight: Common Checks

**Used by:** All E2E tests
**Purpose:** Verify basic environment is healthy before running any test

---

## Checks

### 1. Docker Healthy

**Command:**
```bash
docker compose ps --format json | jq -r '.[].State' | grep -v "running" | wc -l
```

**Pass if:** Output is `0` (all containers running)

**Fail message:** "Docker containers not all running"

---

### 2. Backend API Responsive

**Command:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:${API_PORT:-8000}/health
```

**Pass if:** Output is `200`

**Fail message:** "Backend API not responding"

---

### 3. Sandbox Detection

**Command:**
```bash
if [ -f .env.sandbox ]; then
  source .env.sandbox
  echo "Sandbox: API_PORT=$API_PORT"
else
  echo "Main environment: API_PORT=8000"
fi
```

**Pass if:** Runs without error, sets correct port

**Fail message:** "Unable to detect environment"

---

## Quick Check Script

Run all checks at once:

```bash
#!/bin/bash
set -e

# Load sandbox config if present
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${API_PORT:-8000}

echo "=== Pre-Flight: Common Checks ==="

# Check 1: Docker
UNHEALTHY=$(docker compose ps --format json | jq -r '.[].State' | grep -v "running" | wc -l)
if [ "$UNHEALTHY" -gt 0 ]; then
  echo "FAIL: Docker containers not all running"
  docker compose ps
  exit 1
fi
echo "OK: Docker healthy"

# Check 2: Backend API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$API_PORT/health)
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Backend API not responding (HTTP $HTTP_CODE)"
  exit 1
fi
echo "OK: Backend API responding"

# Check 3: Environment
echo "OK: Using API_PORT=$API_PORT"

echo "=== All pre-flight checks passed ==="
```

---

## Symptom→Cure Mappings

*(Cures will be added in Milestone 3)*

| Symptom | Cause | Cure |
|---------|-------|------|
| Docker containers not running | Docker stopped or crashed | TBD (M3) |
| Backend API not responding | Container starting or crashed | TBD (M3) |
| Wrong port | Sandbox detection failed | TBD (M3) |
```

**Implementation Notes:**
- Checks only, no cures yet (M3 adds cures)
- Script can be run standalone or used by tester agent
- Sandbox-aware from the start (lesson from E2E_CHALLENGES_ANALYSIS.md)

**Acceptance Criteria:**
- [ ] All three checks documented
- [ ] Quick check script is executable
- [ ] Placeholder for cures (M3)
- [ ] Sandbox-aware (reads .env.sandbox)

---

## Milestone 1 Completion Checklist

### All Tasks Complete
- [ ] Task 1.1: Directory structure created
- [ ] Task 1.2: SKILL.md entry point
- [ ] Task 1.3: TEMPLATE.md for new tests
- [ ] Task 1.4: training/smoke.md test recipe
- [ ] Task 1.5: preflight/common.md checks

### E2E Verification
- [ ] Claude can load SKILL.md
- [ ] Claude can navigate to training/smoke test
- [ ] Test recipe has all required sections
- [ ] Pre-flight script runs without errors

### Quality Gates
- [ ] `make quality` passes
- [ ] No lint errors in markdown files
- [ ] All files committed to feature branch
