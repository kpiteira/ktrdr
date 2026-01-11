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

### Next Task Notes

Task 6.2 is verification — run /kdesign-impl-plan on a sample design and verify:
1. Designer is invoked during step 4
2. Designer recommendations are received
3. Milestone output includes E2E Validation section
4. Tests are specific (not generic "run E2E tests")
