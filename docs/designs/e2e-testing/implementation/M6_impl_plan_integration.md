---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: kdesign-impl-plan Integration

**Goal:** Update /kdesign-impl-plan to invoke the e2e-test-designer agent during planning and incorporate test recommendations into milestone plans.

**Branch:** `feature/e2e-framework-m6`

**Builds On:** M5 (Designer Agent)

---

## E2E Test Scenario

**Purpose:** Verify /kdesign-impl-plan invokes designer and includes E2E validation in output.

**Duration:** ~5 minutes (planning session)

**Prerequisites:**
- M5 complete (designer agent works)
- A design document to plan

**Test Steps:**

```markdown
1. Run /kdesign-impl-plan on a small feature
2. During Step 4 (task expansion), impl-plan should:
   a. Identify validation needs for the milestone
   b. Invoke e2e-test-designer with those needs
   c. Receive test recommendations
   d. Include E2E Validation section in milestone output
3. Generated milestone file includes E2E tests to run
```

**Success Criteria:**
- [ ] Impl-plan invokes designer agent
- [ ] Designer recommendations received
- [ ] Milestone output includes E2E Validation section
- [ ] Tests are specific (not generic "run E2E tests")

---

## Task 6.1: Update kdesign-impl-plan Skill

**File:** The kdesign-impl-plan skill (managed skill, needs specific location)

**Type:** CODING

**Task Categories:** Cross-Component, Configuration

**Description:**
Update the /kdesign-impl-plan command to invoke e2e-test-designer during Step 4 (task expansion) for each milestone.

**Integration Points:**

### Step 4 Addition: E2E Test Design

After determining milestone scope and before generating tasks, add:

```markdown
### Step 4.5: E2E Test Design

For each milestone, determine what needs E2E validation:

1. **Identify Validation Needs**
   - What capability does this milestone add?
   - What must work for the milestone to be "done"?
   - What could regress?

2. **Invoke e2e-test-designer**

   Send structured request:
   ```markdown
   ## E2E Test Design Request

   **Milestone:** [name]
   **Capability:** [what user can do when complete]

   **Validation Requirements:**
   1. [Specific thing that must work]
   2. [Another specific thing]

   **Components Involved:**
   - [Component A]
   - [Component B]

   **Intent:** [What we're really validating]
   **Expectations:** [What passing looks like]
   ```

3. **Incorporate Recommendations**

   Add to milestone output:
   ```markdown
   ## E2E Validation

   **Tests to Run (from e2e-test-designer):**

   | Test | Purpose | Notes |
   |------|---------|-------|
   | training/smoke | Verify training works | No regression |

   **Additional Checks (if any):**
   - [Proposed checks from designer]

   **New Test Required (if any):**
   - [Test name and purpose]

   **Execution:** At milestone completion, invoke e2e-tester with above tests.
   ```
```

### Milestone Output Template Update

Update the milestone file template to include E2E Validation section:

```markdown
# Milestone N: [Name]

... existing sections ...

---

## E2E Validation

**Tests to Run:**

| Test | Purpose | Notes |
|------|---------|-------|
| [From designer] | [Purpose] | [Notes] |

**New Tests to Create (if any):**
- [test-name]: [purpose] (building blocks: [list])

**Execution:** After all tasks complete, invoke e2e-tester:
```
Use the e2e-tester agent to run: [test-list]
```

---

## Milestone Completion Checklist

... existing checklist ...
- [ ] E2E tests pass: [test-list]
```

**Implementation Notes:**
- Designer is invoked per milestone (from VALIDATION.md decision)
- Use structured input format from VALIDATION.md
- Include test execution instructions in milestone output

**Acceptance Criteria:**
- [ ] Impl-plan invokes designer at Step 4
- [ ] Input format matches VALIDATION.md contract
- [ ] Milestone output includes E2E Validation section
- [ ] Execution instructions are clear

---

## Task 6.2: Verify Integration Works End-to-End

**File:** N/A (verification task)

**Type:** MIXED

**Task Categories:** Cross-Component

**Description:**
Test the full integration by running /kdesign-impl-plan on a sample feature and verifying E2E validation is included.

**Verification Steps:**

### Setup

Create a simple test design document:

```markdown
# Test Feature Design

## Problem
Add a health check endpoint that returns system status.

## Solution
New endpoint: GET /api/v1/health/detailed
Returns: { services: [...], overall: "healthy" }
```

### Test

1. Run /kdesign-impl-plan on the test design

2. During execution, observe:
   - [ ] Impl-plan identifies validation needs
   - [ ] Impl-plan invokes e2e-test-designer
   - [ ] Designer returns recommendations

3. Check generated milestone file:
   - [ ] E2E Validation section exists
   - [ ] Tests are specific (not generic)
   - [ ] Execution instructions included

4. Verify the E2E Validation section:
   ```markdown
   ## E2E Validation

   **Tests to Run:**
   | Test | Purpose | Notes |
   |------|---------|-------|
   | ... | ... | ... |

   **Execution:** After all tasks complete...
   ```

### Edge Cases

Test with different scenarios:

1. **Feature with existing test coverage:**
   - Designer should find and recommend existing tests

2. **Feature needing new test:**
   - Designer should propose new test structure
   - Milestone should include task to create the test

3. **Feature with partial coverage:**
   - Designer should recommend existing test + additional checks

**Acceptance Criteria:**
- [ ] Integration works end-to-end
- [ ] Designer is invoked correctly
- [ ] Milestone output is complete
- [ ] Edge cases handled appropriately

---

## Milestone 6 Completion Checklist

### All Tasks Complete
- [ ] Task 6.1: kdesign-impl-plan updated with designer integration
- [ ] Task 6.2: End-to-end integration verified

### E2E Verification
- [ ] Run /kdesign-impl-plan → designer invoked
- [ ] Designer recommendations incorporated
- [ ] Milestone output includes E2E Validation section
- [ ] Execution instructions are clear and specific

### Quality Gates
- [ ] `make quality` passes
- [ ] All files committed to feature branch
- [ ] Full planning → testing loop documented

---

## What This Enables

After M6, the planning → testing loop is complete:

```
1. /kdesign-impl-plan runs
2. Designer proposes E2E tests for each milestone
3. Milestones include E2E Validation sections
4. After implementation, Claude sees "Run: training/smoke"
5. Claude invokes e2e-tester
6. Tests run with pre-flight checks
7. Results reported with categories
8. Loop closes: plan → implement → validate
```

This is the core value proposition: Claude is told what tests to run, not left to reinvent them.
