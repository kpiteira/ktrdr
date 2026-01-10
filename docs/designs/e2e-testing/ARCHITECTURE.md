# E2E Testing Framework: Architecture

## Overview

The E2E testing framework uses a **two-agent architecture** backed by a **skill with progressive disclosure**. The key insight: separate design-time concerns (what tests to run) from execution-time concerns (running tests and handling failures).

**Components:**
- **e2e-test-designer** (sub-agent): Researches existing tests, proposes appropriate ones for validation needs
- **e2e-tester** (sub-agent): Executes tests, applies symptom→cure fixes, reports detailed results
- **e2e-testing** (skill): Knowledge base with test recipes, pre-flight modules, patterns, troubleshooting

**Flow:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    PLANNING PHASE                                │
│                                                                  │
│  /kdesign-impl-plan determines what needs validation             │
│           ↓                                                      │
│  Invokes e2e-test-designer sub-agent with validation needs       │
│           ↓                                                      │
│  Designer researches e2e-testing skill, returns recommendations  │
│           ↓                                                      │
│  Impl-plan incorporates into milestone E2E Validation section    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION PHASE                               │
│                                                                  │
│  Claude completes milestone implementation                       │
│           ↓                                                      │
│  Sees E2E Validation section: "Run training/smoke, backtest/x"   │
│           ↓                                                      │
│  Invokes e2e-tester sub-agent with test list                     │
│           ↓                                                      │
│  Tester runs pre-flight → tests → applies cures if needed        │
│           ↓                                                      │
│  Returns detailed PASS/FAIL report to main agent                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Structure

### 1. e2e-test-designer Sub-Agent

**Responsibility:** Research existing tests and propose appropriate ones for validation needs

**Location:** `.claude/agents/e2e-test-designer.md`

**Invoked by:** `/kdesign-impl-plan` during planning phase

**Input:** Clear description of what needs to be validated
```
"Need to validate:
1. Training progress tracking works correctly
2. Training still completes successfully (didn't break existing functionality)
3. Progress updates are visible via operations API"
```

**Process:**
1. Load e2e-testing skill catalog
2. Search for matching test recipes
3. Evaluate fit: does existing test cover the need?
4. If match: return test reference with notes
5. If partial match: return test + additional checks needed
6. If no match: propose new test structure using building blocks

**Output:** Structured recommendations
```markdown
## E2E Validation Recommendations

### Existing Tests That Apply
| Test | Covers | Notes |
|------|--------|-------|
| training/smoke | Basic training works | Run to ensure no regression |
| training/progress | Progress tracking | Directly validates feature |

### Additional Validation Needed
- None - existing tests cover requirements

### OR: New Test Required
- **Name:** training/progress-api
- **Purpose:** Validate progress visible via operations API
- **Building blocks to use:** preflight/common, patterns/poll-progress
- **Proposed structure:** [outline]
```

### 2. e2e-tester Sub-Agent

**Responsibility:** Execute tests, handle failures, report results

**Location:** `.claude/agents/e2e-tester.md`

**Invoked by:** Main coding agent after milestone implementation

**Input:** List of tests to run
```
"Run these E2E tests:
- training/smoke
- training/progress"
```

**Process:**
1. Load e2e-testing skill
2. For each test:
   a. Load test recipe
   b. Run pre-flight checks
   c. If pre-flight fails: apply cure, retry
   d. If pre-flight passes: execute test
   e. Validate success criteria
   f. If test fails: check troubleshooting, apply known cures, retry
3. Compile detailed report

**Output:** Detailed results
```markdown
## E2E Test Results

### training/smoke: ✅ PASSED
- Pre-flight: PASSED (all checks)
- Execution: Completed in 8s
- Evidence: Operation ID op_training_xxx, status=completed
- Logs: "Registered local training bridge" found

### training/progress: ❌ FAILED
- Pre-flight: PASSED
- Execution: FAILED at step 3
- Expected: Progress updates every 5s
- Actual: No progress updates received
- Troubleshooting attempted:
  - Checked Docker logs: No errors found
  - Verified backend mode: Correct (local)
- Likely cause: Progress callback not wired correctly
- Suggested action: Check ProgressBridge registration in TrainingService
```

### 3. e2e-testing Skill (Knowledge Base)

**Responsibility:** Provide test recipes, pre-flight modules, patterns, troubleshooting

**Location:** `.claude/skills/e2e-testing/SKILL.md` + supporting files

**Used by:** Both sub-agents for research and execution

**Structure:** See Directory Structure section below

### 4. /kdesign-impl-plan Integration

**Responsibility:** Invoke e2e-test-designer during planning, incorporate results

**Location:** Updates to `.claude/skills/kdesign-impl-plan/SKILL.md`

**What changes:**
1. After determining milestone scope, impl-plan identifies validation needs
2. Invokes e2e-test-designer sub-agent with validation requirements
3. Designer returns test recommendations
4. Impl-plan incorporates into milestone's "E2E Validation" section

**Example milestone output:**
```markdown
## Milestone 3: E2E Validation

**Tests to Run (from e2e-test-designer):**

| Test | Purpose | Notes |
|------|---------|-------|
| training/smoke | Verify training works | No regression |
| training/progress | Validate progress feature | Feature-specific |

**New Test Required:**
- Create `training/progress-api` using template
- Building blocks: preflight/common, patterns/poll-progress

**Execution:** At milestone completion, invoke e2e-tester with above tests.
```

## e2e-testing Skill Structure

The skill provides the knowledge base that both agents use. Following Claude Code best practices:
- SKILL.md is lean navigation (<500 lines)
- Supporting files loaded on-demand via markdown links
- Scripts for complex logic (zero context cost)

### SKILL.md (Entry Point)

```markdown
# E2E Testing Skill

## Purpose
Knowledge base for E2E test design and execution. Used by:
- e2e-test-designer agent (to find/propose tests)
- e2e-tester agent (to execute tests)

## Test Catalog

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [training/smoke](tests/training/smoke.md) | Training | <30s | Any training changes |
| [training/progress](tests/training/progress.md) | Training | ~60s | Progress tracking |
| [backtest/smoke](tests/backtest/smoke.md) | Backtest | <30s | Any backtest changes |
| ... | ... | ... | ... |

## Supporting Files

### Pre-Flight Modules
- [preflight/common.md](preflight/common.md) - Docker, sandbox (all tests)
- [preflight/training.md](preflight/training.md) - Training-specific checks
- [preflight/backtest.md](preflight/backtest.md) - Backtest-specific checks

### Reusable Patterns
- [patterns/start-and-wait.md](patterns/start-and-wait.md)
- [patterns/poll-progress.md](patterns/poll-progress.md)
- [patterns/check-logs.md](patterns/check-logs.md)

### Troubleshooting (Symptom→Cure)
- [troubleshooting/docker.md](troubleshooting/docker.md)
- [troubleshooting/sandbox.md](troubleshooting/sandbox.md)
- [troubleshooting/training.md](troubleshooting/training.md)

## Creating New Tests
Use [TEMPLATE.md](TEMPLATE.md)
```

### Test Recipes

**Location:** `.claude/skills/e2e-testing/tests/{category}/{name}.md`

Each test recipe is self-contained with:
- Pre-flight checks (links to preflight modules)
- Test execution steps
- Success criteria (including sanity checks)
- Troubleshooting links

### Pre-Flight Modules

**Location:** `.claude/skills/e2e-testing/preflight/`

Each module contains:
- Checks with commands
- **Symptom→Cure mappings** for each failure mode
- "All checks must pass" enforcement

### Reusable Patterns

**Location:** `.claude/skills/e2e-testing/patterns/`

Building blocks that test recipes compose:
- `start-and-wait.md` - Start operation, wait for completion
- `poll-progress.md` - Poll operation progress over time
- `check-logs.md` - Validate expected log entries

### Troubleshooting (Symptom→Cure)

**Location:** `.claude/skills/e2e-testing/troubleshooting/`

Known problems with known solutions. Format:
```
**Symptom:** [What you observe]
**Cause:** [Why this happens]
**Cure:** [Exact commands to fix]
**Prevention:** [How to avoid]
```

### Template

**Location:** `.claude/skills/e2e-testing/TEMPLATE.md`

Used by e2e-test-designer when proposing new tests.

## Directory Structure

```
.claude/
├── agents/
│   ├── e2e-test-designer.md    # Design-time: research & propose tests
│   └── e2e-tester.md           # Execution-time: run tests & report
└── skills/
    └── e2e-testing/
        ├── SKILL.md            # Entry point, catalog (<500 lines)
        ├── TEMPLATE.md         # Template for new tests
        ├── tests/
        │   ├── training/
        │   │   ├── smoke.md
        │   │   └── progress.md
        │   ├── backtest/
        │   │   └── smoke.md
        │   └── data/
        │       └── cache.md
        ├── preflight/
        │   ├── common.md       # Docker, sandbox (all tests)
        │   ├── training.md
        │   └── backtest.md
        ├── patterns/
        │   ├── start-and-wait.md
        │   ├── poll-progress.md
        │   └── check-logs.md
        └── troubleshooting/
            ├── docker.md
            ├── sandbox.md
            └── training.md
```

## Integration Points

### 1. /kdesign-impl-plan → e2e-test-designer

**How impl-plan uses the designer agent:**

```
1. Impl-plan identifies validation needs for milestone
2. Invokes e2e-test-designer sub-agent:
   "Need to validate: [specific requirements]"
3. Designer loads e2e-testing skill, researches
4. Designer returns: matching tests OR new test proposal
5. Impl-plan incorporates into milestone E2E Validation section
```

### 2. Main Agent → e2e-tester

**How main agent uses the tester agent:**

```
1. Main agent completes milestone implementation
2. Reads E2E Validation section from plan
3. Invokes e2e-tester sub-agent:
   "Run tests: training/smoke, backtest/smoke"
4. Tester loads skill, runs tests, handles failures
5. Tester returns detailed PASS/FAIL report
6. Main agent decides next steps based on report
```

### 3. /ktask (Optional Enhancement)

After task implementation, ktask could suggest:
"This modified training code. Invoke e2e-tester for training/smoke?"

Not required for MVP.

## Migration Plan

### Phase 1: Framework Setup
- Create agent definitions (e2e-test-designer.md, e2e-tester.md)
- Create skill directory structure
- Create SKILL.md with catalog
- Create TEMPLATE.md
- Create preflight/common.md with symptom→cure mappings

### Phase 2: Migrate Core Tests from SCENARIOS.md
- Extract training smoke test → tests/training/smoke.md
- Extract backtest smoke test → tests/backtest/smoke.md
- Extract relevant patterns → patterns/
- Extract troubleshooting content from E2E_CHALLENGES_ANALYSIS.md → troubleshooting/

### Phase 3: Update /kdesign-impl-plan
- Add logic to invoke e2e-test-designer during planning
- Include E2E Validation section in milestone output
- Test with a real milestone

### Phase 4: Validate & Iterate
- Run through a complete milestone with new framework
- Test both agents work correctly
- Identify gaps, missing symptom→cure mappings
- Archive old docs/testing/ content

## Verification Strategy

### e2e-test-designer Agent
**Verification:** Given validation requirements, returns appropriate test recommendations or new test proposals

### e2e-tester Agent
**Verification:** Executes tests, applies cures on pre-flight failures, returns detailed reports

### Progressive Disclosure
**Verification:** Agents load only specific supporting files needed, not entire skill

### Pre-Flight Effectiveness
**Verification:** Known environment issues (Docker down, wrong port) caught with cures applied

### Symptom→Cure
**Verification:** When failures occur, known cures are applied automatically before escalating
