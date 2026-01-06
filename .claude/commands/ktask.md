# Task Implementation Command

Implements tasks from a vertical implementation plan using TDD methodology.

This command embodies our partnership values from CLAUDE.md — craftsmanship over completion, honesty over confidence, decisions made together.

---

## Command Usage

```
/ktask impl: <plan.md> task: <task-id> [design: <design.md>] [arch: <architecture.md>]
```

**Required:**
- `impl:` — Implementation plan (from `/kdesign-impl-plan`)
- `task:` — Task ID, milestone, or range (e.g., "M1", "2.3", "Phase 2")

**Optional:**
- `design:` — Design document (overrides frontmatter)
- `arch:` — Architecture document (overrides frontmatter)
- Additional reference docs as needed

### Context Document Resolution

The command automatically discovers design/architecture docs:

1. **Parse frontmatter** from the implementation plan file
2. **If frontmatter has refs** → use them automatically
3. **If CLI params provided** → they override frontmatter
4. **If neither** → fail with: "No design/architecture docs found. Add frontmatter to plan or pass design:/arch: params"

**Frontmatter example** (in milestone file):

```markdown
---
design: docs/designs/feature-name/DESIGN.md
architecture: docs/designs/feature-name/ARCHITECTURE.md
---
```

---

## Workflow Overview

```
1. Setup       → Retrieve task, verify branch, classify type
2. Research    → Read docs, check handoffs, summarize approach
3. Implement   → TDD cycle (coding tasks only)
4. Verify      → Integration test, acceptance criteria, quality gates
5. E2E Test    → MILESTONE COMPLETE: Run E2E scenario (MANDATORY)
6. Complete    → HANDOFF UPDATE (MANDATORY), task summary
```

**Two steps are MANDATORY and must not be skipped:**
- **E2E Test (Step 5)**: When completing ANY task that is the LAST task in a milestone
- **Handoff Update (Step 6)**: After EVERY task (not just milestones)

---

## 1. Setup

### Retrieve Task

Extract the task from the implementation plan. Display:
- Task title and description
- Acceptance criteria
- Files to create/modify
- **Is this the last task in the milestone?** (If YES, you MUST run E2E tests)
- E2E test scenario location (if this completes a milestone)

**IMPORTANT**: If this is the last task in a milestone, IMMEDIATELY note that you will need to run E2E tests after implementation. Add a reminder to yourself in the task notes.

If validation output is provided, review key decisions to ensure consistency with resolved gaps.

### Verify Branch

Check task description for branch instructions:
- "Create new branch: [name]"
- "Work on branch: [name]"
- "Branch strategy: [description]"

If no branch strategy is specified, ask before proceeding.

### Classify Task Type

State the classification explicitly:

- **CODING** — Implementation work. TDD is required.
- **RESEARCH** — Investigation, analysis, documentation. No TDD.
- **MIXED** — Research first, then TDD for implementation portion.

### Check Handoffs

Look for `HANDOFF_*.md` in the implementation plan directory. If present, read and note:
- Critical gotchas from previous tasks
- Emergent patterns to follow
- Workarounds for known issues

---

## 2. Research Phase (All Tasks)

Before writing any code:

1. **Read context documents** — Design doc and architecture doc (from frontmatter or params), relevant sections of implementation plan
2. **Identify existing patterns** — Find similar code in the codebase to follow
3. **Locate dependencies** — Files, classes, functions that will be involved
4. **Note integration points** — How this task connects to other components

**Output:** Brief summary (2-4 sentences) covering:
- Design intent
- Architecture approach  
- Implementation approach

Do not write implementation code during this phase.

---

## 3. Implementation (Coding Tasks Only)

Follow the TDD cycle: **RED → GREEN → REFACTOR**

### RED: Write Failing Tests

Before any implementation:

1. Create test file(s) following project conventions
2. Write tests covering:
   - Happy path (normal operation)
   - Error cases (failures, exceptions)
   - Edge cases (boundaries, null values)
3. Run tests: `make test-unit`
4. Verify tests fail meaningfully (not import errors)

Show output: "✅ Tests written and failing as expected"

If you catch yourself writing implementation before tests, stop, delete the implementation code, and return to this phase.

### GREEN: Minimal Implementation

1. Write just enough code to make tests pass
2. Follow existing patterns in the codebase
3. Run tests frequently during implementation
4. Don't over-engineer or add untested features

Show output: "✅ All tests passing"

### REFACTOR: Improve Quality

1. Improve code clarity and maintainability
2. Extract common patterns
3. Add documentation and type hints
4. Run tests after each refactoring: `make test-unit`
5. Run quality checks: `make quality`

Show output: "✅ Tests and quality checks passing"

---

## 4. Verification

### Integration Smoke Test

Unit tests verify components in isolation. Integration tests verify they work together. Passing unit tests ≠ working system.

For detailed patterns and API references, use the **integration-testing skill**.

After unit tests pass (for changes affecting system behavior):

1. **Start system**: `docker compose up -d`
2. **Execute modified flow**: Use CLI commands or curl/API calls
3. **Verify end-to-end**: Does the operation complete? Is state consistent?
4. **Check logs**: `docker compose logs backend --since 5m | grep -i error`
5. **Report**: "✅ Integration test passed" or "❌ Issue found: [description]"

**Skip integration testing for:**
- Pure refactoring with no behavior change
- Documentation-only changes
- Test-only changes

If integration test fails, investigate and fix before proceeding. The issue is likely architectural, not just code.

### Milestone E2E Test (MANDATORY FOR LAST TASK IN MILESTONE)

**REQUIRED**: When you complete the LAST task in a milestone, you MUST run the milestone's E2E test scenario.

**How to identify:**
- Check the implementation plan - is this the final task listed for the milestone?
- Does the task description say "completes milestone M1/M2/etc"?
- Is there an E2E test scenario in the milestone documentation?

**If YES to any above:**

1. **Locate E2E test**: Find the test scenario in the milestone plan (usually at end of file)
2. **Run the test**: Execute the full scenario step-by-step
3. **Report results**: Document pass/fail for each test step
4. **Fix failures**: Do NOT proceed if E2E tests fail - investigate and fix

**This is NOT optional.** E2E tests validate the full user journey and catch integration issues that unit tests miss.

**Example locations for E2E tests:**
- End of milestone implementation file (e.g., `M1_config_loading.md`)
- Dedicated `E2E_TESTS.md` file in the design directory
- `## E2E Test Scenario` section in the plan

### Acceptance Criteria Validation

Go back to the task description. For each acceptance criterion:

1. Identify the type (feature, unit test, integration test, performance, documentation)
2. Validate it appropriately
3. Check it off with status

```markdown
- [x] Acceptance criterion 1 — ✅ VALIDATED
- [x] Acceptance criterion 2 — ✅ VALIDATED  
- [ ] Acceptance criterion 3 — ❌ NOT MET (needs: ...)
```

If any criterion is not met, continue working before proceeding.

### Quality Gates

All must pass before completion:

- [ ] All unit tests pass: `make test-unit`
- [ ] Quality checks pass: `make quality`
- [ ] Code is documented (docstrings explaining "why")
- [ ] All work is committed with clear messages
- [ ] No security vulnerabilities introduced
- [ ] **E2E test passed** (if this is the last task in a milestone)
- [ ] **Handoff document updated** (EVERY task - see Completion section)

---

## 5. Completion

### Handoff Document (MANDATORY - DO THIS FIRST)

**REQUIRED AFTER EVERY TASK**: You MUST update the handoff document before writing the task summary.

**Action steps:**

1. **Locate handoff file**: `HANDOFF_<phase/feature>.md` in the implementation plan directory
   - Example: `docs/designs/strategy-grammar-v3/implementation/HANDOFF_M1.md`
   - If it doesn't exist, CREATE it

2. **Add section for this task**: Add a new section titled `## Task X.Y Complete: [Task Name]`

3. **Document learnings** (only if it saves time for next implementer):
   - **Gotchas**: Problem + symptom + solution (e.g., "TimeframeConfiguration is not subscriptable - use .timeframes")
   - **Workarounds**: Non-obvious solutions to constraints
   - **Emergent patterns**: Architectural decisions made during implementation
   - **Implementation notes**: Key patterns or approaches that worked well

4. **Add "Next Task Notes"**: Brief guidance for the next task (what files to import, what to watch out for)

**EXCLUDE** (wastes tokens):
- Task completion status (already in plan)
- Process steps (already in this command)
- Test counts or coverage numbers (observable)
- File listings (observable from codebase)

**Target size**: Under 100 lines total for the entire handoff file.

**Why this matters**: You consistently find handoff documents useful when starting tasks. Creating them ensures the next task (even if it's you in a new session) benefits from your learnings.

### Task Summary

Provide a summary of what was accomplished:

```markdown
## Task Complete: [Task ID]

**What was implemented:**
- [Brief description of the change]

**Files changed:**
- [List of files created/modified/deleted]

**Key decisions made:**
- [Any non-obvious choices and why]

**Issues encountered:**
- [Problems hit and how they were resolved, or "None"]
```

This summary is displayed to the human (or orchestrator) and provides visibility into what happened during the task.

**Note:** PR creation is handled at milestone level, not per-task. Commits should be made after each task, but PRs are created when the full milestone is complete.

---

## Error Handling

If you encounter blockers:

- Do not mark task as complete
- Keep task in "doing" status
- Document the blocker
- Ask for guidance on how to proceed

---

## Task Instructions Override

If task-specific instructions contradict this command, follow the task instructions. Tasks may have context that requires different approaches.

---

## Multiple Tasks

When given multiple tasks (a milestone or phase):

1. Implement in the order specified in the plan
2. Each task follows the full workflow above
3. **Update handoff after EACH task** (not just at the end)
4. Commit after each task (not just at the end)
5. **MANDATORY: Run the milestone's E2E test after completing the LAST task**
   - This is NOT optional
   - Do NOT skip this step
   - E2E tests are in the milestone plan documentation

---

## Quick Reference

| Phase | Key Actions | Output |
|-------|-------------|--------|
| Setup | Retrieve, branch, classify, handoffs | Task details displayed |
| Research | Read docs, find patterns | 2-4 sentence summary |
| RED | Write tests, run, verify fail | "✅ Tests failing as expected" |
| GREEN | Implement, run tests | "✅ All tests passing" |
| REFACTOR | Clean up, quality checks | "✅ Tests and quality passing" |
| Integration | Start system, execute flow, check logs | "✅ Integration passed" |
| Acceptance | Validate each criterion | Checklist with status |
| Quality | Tests, quality, commits, **E2E (if milestone)** | All gates passed |
| **E2E Test** | **Run milestone E2E scenario (last task only)** | **"✅ E2E test passed"** |
| **Handoff** | **Update HANDOFF_*.md (EVERY task)** | **Section added to handoff** |
| Summary | Write task completion summary | Task summary with changes/decisions |
