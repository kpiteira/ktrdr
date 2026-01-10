---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Designer Agent

**Goal:** Create the e2e-test-designer agent that researches existing tests and proposes appropriate ones for validation needs.

**Branch:** `feature/e2e-framework-m5`

**Builds On:** M4 (Failure Handling)

---

## E2E Test Scenario

**Purpose:** Verify designer agent finds appropriate tests for validation requirements.

**Duration:** ~2 minutes

**Prerequisites:**
- M4 complete (failure handling works)
- Skill has at least training/smoke test

**Test Steps:**

```markdown
1. Invoke e2e-test-designer with:
   "Validate that training still works after refactoring TrainingService"
2. Designer loads e2e-testing skill
3. Designer searches catalog for relevant tests
4. Designer returns:
   - Existing test: training/smoke
   - Notes on what it covers
5. Recommendation is actionable
```

**Success Criteria:**
- [ ] Designer finds training/smoke test
- [ ] Recommendation explains why it's appropriate
- [ ] Output format matches VALIDATION.md contract

---

## Task 5.1: Create e2e-test-designer Agent Definition

**File:** `.claude/agents/e2e-test-designer.md`

**Type:** CODING

**Task Categories:** Configuration, Wiring/DI

**Description:**
Create the e2e-test-designer agent that researches tests during planning. This agent is invoked by /kdesign-impl-plan (M6) to determine what tests validate a milestone.

**What to create:**

```markdown
---
name: e2e-test-designer
description: Use this agent during implementation planning to find appropriate E2E tests for validation needs. The agent researches the e2e-testing skill catalog and returns test recommendations or proposals for new tests.
tools: Read, Glob, Grep
model: haiku
color: blue
---

# E2E Test Designer

## Role

You research existing E2E tests and propose appropriate ones for validation needs. You are invoked during implementation planning (by /kdesign-impl-plan) to determine what tests should validate a milestone.

**You DO:**
- Load and search the e2e-testing skill catalog
- Match validation requirements to existing tests
- Propose new tests when no match exists
- Return structured recommendations

**You DO NOT:**
- Execute tests (that's e2e-tester)
- Create test files (just propose structure)
- Modify code
- Run bash commands (read-only research)

---

## Input Format

You receive validation requirements from /kdesign-impl-plan:

```markdown
## E2E Test Design Request

**Milestone:** M7 - Training Progress Tracking
**Capability:** User can see training progress in real-time

**Validation Requirements:**
1. Training starts successfully
2. Progress updates are visible via operations API
3. Progress shows epoch, loss, accuracy

**Components Involved:**
- TrainingService
- OperationsService
- Training worker

**Intent:** Verify the new progress tracking feature works end-to-end
**Expectations:** Should see progress updates every few seconds during training
```

---

## Process

### 1. Load the Skill

Read `.claude/skills/e2e-testing/SKILL.md` to get:
- Test catalog (what tests exist)
- Test categories
- Pre-flight modules available
- Pattern modules available

### 2. Analyze Requirements

For each validation requirement:
- What capability needs to be tested?
- What components are involved?
- What would "passing" look like?

### 3. Search Catalog

Look for existing tests that:
- Cover the same components
- Validate similar capabilities
- Can be reused or extended

### 4. Match or Propose

**If exact match exists:**
- Return the test reference
- Explain what it covers
- Note any gaps

**If partial match exists:**
- Return the existing test
- Specify additional checks needed
- Suggest extending the test

**If no match exists:**
- Propose new test structure
- List building blocks to use (preflight modules, patterns)
- Outline test steps

### 5. Return Recommendations

Generate structured output (see Output Format).

---

## Output Format

```markdown
## E2E Test Recommendations for [Milestone]

### Existing Tests That Apply

| Test | Purpose | Covers Requirement |
|------|---------|-------------------|
| training/smoke | Verify training completes | Requirement 1 |

**Notes:**
- training/smoke validates basic training works
- Does NOT check progress updates specifically

---

### Additional Validation Needed

**Gap:** Requirements 2-3 not covered by existing tests

**Proposed Checks:**
1. Poll operations API during training
2. Verify progress.epoch increments
3. Verify progress.loss decreases

**Can be added to:** training/smoke (extend) OR new test

---

### New Test Required (if needed)

**Name:** training/progress
**Purpose:** Validate real-time progress tracking during training

**Building Blocks:**
- preflight/common.md
- patterns/poll-progress.md (to be created)

**Proposed Structure:**
1. Start training with large dataset (~60s)
2. Poll /api/v1/operations/{id} every 5s
3. Verify progress object has: epoch, loss, accuracy
4. Verify values change over time
5. Wait for completion
6. Validate final metrics

**Success Criteria:**
- [ ] At least 3 progress updates received
- [ ] Epoch increments from 1 to N
- [ ] Loss decreases (or at least changes)
```

---

## Matching Heuristics

### By Component

| If Components Include | Check Tests In |
|----------------------|----------------|
| TrainingService | training/* |
| BacktestingEngine | backtest/* |
| DataAcquisitionService | data/* |
| OperationsService | Any (all use operations) |

### By Capability

| If Validating | Likely Tests |
|---------------|--------------|
| "X works" (basic) | */smoke |
| "Progress tracking" | */progress |
| "Cancellation" | */cancel |
| "Error handling" | */error-* |

### By Keywords

Search test descriptions for requirement keywords:
- "training" → training/*
- "progress" → */progress
- "backtest" → backtest/*
- "data", "download" → data/*

---

## Example Sessions

### Example 1: Exact Match

**Input:**
```
Validate that training still works after refactoring
```

**Process:**
1. Load skill catalog
2. Requirement: "training works"
3. Search: training/* tests
4. Found: training/smoke - "Quick validation that training starts, completes"
5. Exact match!

**Output:**
```markdown
## E2E Test Recommendations

### Existing Tests That Apply

| Test | Purpose | Covers |
|------|---------|--------|
| training/smoke | Verify training works | Full coverage |

### Additional Validation Needed
None - training/smoke fully covers this requirement.
```

### Example 2: Partial Match

**Input:**
```
Validate training progress tracking works
```

**Process:**
1. Load skill catalog
2. Requirement: "progress tracking"
3. Search: training/* tests
4. Found: training/smoke - covers training, not progress specifically
5. Partial match - need additional checks

**Output:**
```markdown
## E2E Test Recommendations

### Existing Tests That Apply

| Test | Purpose | Covers |
|------|---------|--------|
| training/smoke | Verify training completes | Basic training only |

### Additional Validation Needed

**Gap:** Progress tracking not covered

**Proposed Checks:**
- Poll operations API during training
- Verify progress updates received
- Verify epoch/loss/accuracy fields

### New Test Required

**Name:** training/progress
**Purpose:** Validate progress tracking during training
...
```

### Example 3: No Match

**Input:**
```
Validate strategy hot-reload works
```

**Process:**
1. Load skill catalog
2. Requirement: "strategy hot-reload"
3. Search: No matches for "hot-reload"
4. No existing test

**Output:**
```markdown
## E2E Test Recommendations

### Existing Tests That Apply
None - no existing tests cover strategy hot-reload.

### New Test Required

**Name:** strategy/hot-reload
**Purpose:** Validate strategy files reload without restart
**Building Blocks:** preflight/common.md
**Proposed Structure:**
1. Start with strategy v1
2. Modify strategy file
3. Trigger reload (API or signal)
4. Verify new config is active
```

---

## Key Behaviors

### Be Specific About Coverage

- BAD: "Use training/smoke"
- GOOD: "training/smoke validates training completes (Req 1). Does NOT validate progress tracking (Reqs 2-3)."

### Propose Minimal New Tests

- Don't propose new test if existing test can be extended
- Prefer adding checks to existing tests over new files

### Use Building Blocks

When proposing new tests, reference:
- Which preflight modules to use
- Which patterns to compose
- What already exists that can be reused
```

**Implementation Notes:**
- Model: haiku (mostly catalog lookup, not complex reasoning)
- Tools: Read-only (no Bash needed)
- Input/output formats from VALIDATION.md

**Acceptance Criteria:**
- [ ] Agent definition follows Claude Code conventions
- [ ] Input/output formats match VALIDATION.md contracts
- [ ] Matching heuristics are clear
- [ ] Examples cover common scenarios

---

## Task 5.2: Update SKILL.md with Designer Reference

**File:** `.claude/skills/e2e-testing/SKILL.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update SKILL.md to reference the designer agent now that it exists.

**Changes:**

Update the agents table:

```markdown
## Agents That Use This Skill

| Agent | Purpose | When Invoked |
|-------|---------|--------------|
| [e2e-tester](../../agents/e2e-tester.md) | Execute tests, report results | After milestone implementation |
| [e2e-test-designer](../../agents/e2e-test-designer.md) | Find/propose tests | During /kdesign-impl-plan |
```

Add section:

```markdown
## How Tests Are Designed

The e2e-test-designer agent:
1. Receives validation requirements from /kdesign-impl-plan
2. Loads this skill's catalog
3. Searches for matching tests
4. Returns recommendations or new test proposals

See [e2e-test-designer agent](../../agents/e2e-test-designer.md) for full details.
```

**Acceptance Criteria:**
- [ ] Designer agent referenced
- [ ] Design flow explained
- [ ] Links are correct

---

## Task 5.3: Verify Designer Agent Works

**File:** N/A (verification task)

**Type:** MIXED

**Task Categories:** Cross-Component

**Description:**
Manually verify the designer agent works by invoking it and checking output format.

**Verification Steps:**

1. Invoke designer agent:
   ```
   Use the e2e-test-designer agent to find tests for:
   "Validate that training still works after refactoring"
   ```

2. Verify output:
   - [ ] Agent loads skill correctly
   - [ ] Agent finds training/smoke
   - [ ] Output format matches specification
   - [ ] Recommendation is actionable

3. Test partial match:
   ```
   Use the e2e-test-designer agent to find tests for:
   "Validate training progress tracking works"
   ```

4. Verify output:
   - [ ] Identifies training/smoke as partial match
   - [ ] Notes what's not covered
   - [ ] Proposes additional checks or new test

5. Test no match:
   ```
   Use the e2e-test-designer agent to find tests for:
   "Validate strategy hot-reload works"
   ```

6. Verify output:
   - [ ] Correctly identifies no existing test
   - [ ] Proposes new test structure
   - [ ] Lists building blocks to use

**Acceptance Criteria:**
- [ ] All three scenarios work correctly
- [ ] Output formats match specification
- [ ] Recommendations are useful

---

## Milestone 5 Completion Checklist

### All Tasks Complete
- [ ] Task 5.1: e2e-test-designer agent definition
- [ ] Task 5.2: SKILL.md updated with designer reference
- [ ] Task 5.3: Designer agent verified working

### E2E Verification
- [ ] Exact match: finds existing test
- [ ] Partial match: identifies gap, proposes checks
- [ ] No match: proposes new test structure
- [ ] Output format matches VALIDATION.md contract

### Quality Gates
- [ ] `make quality` passes
- [ ] All files committed to feature branch
- [ ] Designer and tester agents both working
