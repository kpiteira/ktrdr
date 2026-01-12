# Handoff: Milestone 6 - kdesign-impl-plan Integration

## Task 6.1 Complete: Update kdesign-impl-plan Skill

**File:** `.claude/commands/kdesign-impl-plan.md`

### What Was Added

1. **Step 4.6: E2E Test Design** — New step after Step 4.5 (Test Requirement Analysis)
   - 4.6.1: Invoke e2e-test-designer with structured input
   - 4.6.2: Handle designer response (match found OR architect handoff)
   - 4.6.3: Incorporate into milestone output

2. **E2E Validation Section Format** — Template for milestone files
   - Tests to Run table (test name, purpose, source)
   - Coverage Notes
   - New Test Specification (if architect was invoked)
   - Pre-Execution Task (if test file needs creation)
   - Execution instructions

3. **Integration with Other Commands** — Updated flow diagram
   - Now shows e2e-test-designer and e2e-test-architect in the pipeline
   - Added step 4 for e2e-tester at milestone completion

### Gotchas

**Input format is critical.** The designer expects this exact structure:
```markdown
## E2E Test Design Request

**Milestone:** [name/number]
**Capability:** [what user can do when complete]

**Validation Requirements:**
1. [Specific thing that must work]

**Components Involved:**
- [Component A]

**Intent:** [Free-form]
**Expectations:** [Free-form]
```

**Two response types.** Designer returns EITHER:
- Existing tests with coverage notes (no architect needed)
- "Architect Handoff Required" with structured context (invoke architect)

---

## Task 6.2 Complete: End-to-End Integration Verified

### Verification Results

Three scenarios tested by invoking e2e-test-designer directly:

| Scenario | Input | Result |
|----------|-------|--------|
| Exact match | Training validation | Found training/smoke, full coverage |
| Partial match | Health endpoint | Found existing test + identified gaps |
| No match | Strategy hot-reload | Produced architect handoff |

### Observations

**Designer (haiku) works well:**
- Fast response times
- Correctly identifies existing tests
- Produces structured handoffs when no match
- Coverage analysis is specific and actionable

**Handoff format is complete:**
- Preserves all original context
- Lists available building blocks
- References similar tests
- Includes implementation considerations

### E2E Test Scenario: ✅ PASSED

All success criteria met:
- [x] Impl-plan invokes designer agent (Step 4.6 added)
- [x] Designer recommendations received (all 3 scenarios worked)
- [x] Milestone output includes E2E Validation section (template defined)
- [x] Tests are specific (training/smoke, gap analysis, full specs)

---

## M6 Milestone Complete

All tasks completed:
- [x] Task 6.1: kdesign-impl-plan updated with Step 4.6 and E2E Validation section
- [x] Task 6.2: End-to-end integration verified with 3 scenarios

### What's Now Possible

The planning → testing loop is complete:

```
1. /kdesign-impl-plan runs
2. For each milestone, invokes e2e-test-designer (Step 4.6)
3. Designer finds existing tests OR hands off to architect
4. Architect designs new test if needed
5. Milestone output includes E2E Validation section with:
   - Specific tests to run
   - Coverage notes
   - New test specifications (if architect was invoked)
   - Pre-execution task for test file creation
6. After implementation, invoke e2e-tester with test list
```

### For M7

M7 harvests E2E content from existing implementation plans and handoffs. See VALIDATION.md for scope and context management warnings.
