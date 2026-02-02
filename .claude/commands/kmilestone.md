# Milestone Execution Command

Executes an entire milestone by invoking `/ktask` for each task, with context compaction between tasks.

---

## Command Usage

```
/kmilestone @<milestone_file.md> [--from <task_id>]
```

**Required:**
- `@milestone_file.md` — The milestone implementation plan (e.g., `@M4_cleanup.md`)

**Optional:**
- `--from <task_id>` — Start from specific task (default: auto-detect from handoff)

---

## The One Rule

**kmilestone invokes ktask. ktask does the work.**

You are an orchestrator. Your job is to invoke `/ktask` for each task, verify completion, and manage context. You do NOT implement tasks directly.

---

## Workflow

### 1. Initialize

Parse the milestone and determine starting point.

**Actions:**
1. Extract task list from `## Task X.Y` headings in milestone file
2. Locate handoff file: `HANDOFF_<milestone>.md` in same directory
3. Parse handoff for "Task X.Y Complete" sections
4. Identify first incomplete task

**Output:**
```
Milestone: M4 - Cleanup (6 tasks)
Completed: 4.1, 4.2 (from handoff)
Starting from: 4.3
```

**Initialize tracking:**
- `e2e_tests`: List to capture E2E test results from VALIDATION tasks
- `challenges`: List to capture challenges/solutions from each task

---

### 2. Execute Each Task (MANDATORY: Use ktask)

For each remaining task, follow this loop:

#### Step 2a: Invoke ktask (MANDATORY)

**You MUST invoke ktask. NEVER implement tasks directly.**

**For CODING/RESEARCH/MIXED tasks:**
```
/ktask impl: <milestone_file> task: <task_id>
```

**For VALIDATION tasks — include E2E reminder:**
```
/ktask impl: <milestone_file> task: <task_id>

REMINDER: This is a VALIDATION task. You MUST use the E2E agent workflow:
e2e-test-designer → e2e-test-architect → e2e-tester
Do NOT run bash commands directly from the milestone file.
```

**CRITICAL: What makes a valid VALIDATION task:**

VALIDATION must test **real operational flows**, not just "does it start?":

| ❌ Insufficient | ✅ Valid |
|-----------------|----------|
| "API imports without error" | "Training completes and produces a model file" |
| "System starts" | "Backtest executes and produces trades > 0" |
| "No exceptions on startup" | "Full workflow completes with verifiable output" |

A validation that only checks "the code runs without crashing" will miss:
- Save/load bugs that only appear when data flows end-to-end
- Config mismatches between components
- Missing dependencies only needed at runtime

**If a milestone changes how components interact, the validation MUST exercise that interaction with real data.**

Example:
```
/ktask impl: docs/designs/indicator-fuzzy-cleanup/implementation/M4_cleanup.md task: 4.3
```

Wait for ktask to complete fully before proceeding.

#### Step 2b: Verify Completion

After ktask finishes, verify:

- [ ] Handoff file has new "Task X.Y Complete" section?
- [ ] `make test-unit` passes?
- [ ] `make quality` passes?
- [ ] Changes committed?

If any check fails, ktask did not complete properly. Investigate before continuing.

#### Step 2c: Capture Task Learnings

After each task completes, extract and record:

**For VALIDATION tasks — capture E2E test results:**
- Test name (e.g., `cli/kinfra-spec-workflow`)
- Number of steps executed
- Result (PASSED/FAILED)

**For ALL tasks — capture challenges encountered:**
- Read the new handoff section for this task
- Extract any challenges/gotchas mentioned and their solutions
- Record as: `{task_id, challenge, solution}`

Example challenges to look for:
- "X didn't work because Y, so we did Z instead"
- "Gotcha: [problem] — solution: [fix]"
- "Task was already complete because..."
- Any workaround or non-obvious decision

#### Step 2d: Run Unit Test Quality Check (CODING tasks only)

For CODING tasks, invoke the quality checker:

```
Task(
    subagent_type="unit-test-quality-checker",
    prompt="Check tests modified in task <task_id>: <list test files>"
)
```

If issues found: fix and re-check (up to 2 retries).

#### Step 2e: Continue to Next Task

Proceed directly to the next task. Do NOT pause to ask for `/compact` between tasks.

If context becomes too large during execution, you may ask the user to run `/compact` at that point.

---

### 3. Complete Milestone

After all tasks complete, produce an enhanced summary with tracked data:

```
## Milestone Complete: M4 - Cleanup

**Tasks completed:** 4.1 through 4.6
**Quality gates:** All passed

**Handoff:** docs/designs/.../HANDOFF_M4.md

### E2E Tests Performed

| Test | Steps | Result |
|------|-------|--------|
| cli/kinfra-spec-workflow | 8 | ✅ PASSED |
| infra/sandbox-init | 5 | ✅ PASSED |

### Challenges & Solutions

| Task | Challenge | Solution |
|------|-----------|----------|
| 4.1 | stderr not captured in test output | Used typer.secho() to stdout instead |
| 4.3 | Task already complete from earlier task | Added unit tests to validate existing code |
| 4.5 | No existing E2E test in catalog | Designed new test via e2e-test-architect |

Ready for PR creation.
```

**Notes on the summary tables:**

- **E2E Tests Performed**: Include ALL tests run during VALIDATION tasks. If multiple tests were run, list each one.
- **Challenges & Solutions**: Aggregate from all tasks. Only include actual challenges (not routine work). This helps with:
  - PR descriptions (copy directly)
  - Future debugging (what went wrong before)
  - Process improvement (recurring issues)

---

## Anti-Patterns (NEVER Do These)

| Anti-Pattern | Why It's Wrong | Do This Instead |
|--------------|----------------|-----------------|
| ❌ Implementing tasks directly | Bypasses TDD, handoffs, quality gates | Invoke `/ktask` |
| ❌ Running E2E bash commands manually | Skips e2e-tester agent validation | Include E2E reminder when invoking ktask for VALIDATION tasks |
| ❌ Skipping handoff verification | Next task loses context | Always verify handoff updated |
| ❌ Batching multiple tasks | Loses per-task verification | One ktask invocation per task |
| ❌ Accepting "files don't exist" without verification | Research errors get hidden | See Guardrail section below |

---

## Guardrail: Unexpected Findings

If ktask reports something that contradicts task assumptions, **do not proceed blindly**.

Examples of unexpected findings:
- "Files mentioned in task don't exist"
- "Pattern not found in codebase"
- "Code is already fixed / task already complete"
- Anything else that seems odd during research or implementation

**When this happens:**

1. **Ask ktask to double-check** with alternative search methods
2. **If still unexpected, escalate to user**: "Task 4.1 references 8 files but I only found 4. Should I proceed with what exists, or is something wrong?"

Research errors are dangerous because they're silent. A wrong conclusion ("files don't exist") leads to skipped work or wrong implementations. Always verify unexpected findings before proceeding.

---

## Resume Behavior

kmilestone is idempotent. Running it again:

1. Parses handoff file
2. Finds completed tasks
3. Resumes from first incomplete task

**Force restart:** `--from 4.1` ignores handoff and starts fresh.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| ktask fails quality gates | ktask handles retry internally |
| ktask reports blocker | Stop, report to user, await guidance |
| Handoff not updated after ktask | Error — ktask did not complete. Investigate. |
| ktask reports unexpected finding | Double-check, then escalate to user if still odd |
| Context becomes too large | Ask user to run `/compact`, then continue |

---

## Quick Reference

| Phase | Action | Output |
|-------|--------|--------|
| **Initialize** | Parse milestone + handoff | "Starting from: X.Y" |
| **Per-task** | `/ktask impl: <file> task: <id>` | ktask completes task |
| **VALIDATION task** | Include E2E reminder in ktask invocation | ktask uses e2e agents |
| **Verify** | Check handoff, tests, quality | All checks pass |
| **Capture** | Record E2E results + challenges | Update tracking lists |
| **Quality check** | unit-test-quality-checker (CODING) | No issues found |
| **Complete** | Report summary with tables | E2E tests + Challenges tables |

---

## Example Execution

```
User: /kmilestone @docs/designs/feature/implementation/M3_core.md

Claude:
Milestone: M3 - Core Implementation (5 tasks)
Completed: 3.1 (from handoff)
Starting from: 3.2

---

Invoking ktask for Task 3.2...

/ktask impl: docs/designs/feature/implementation/M3_core.md task: 3.2

[ktask runs full workflow: Setup → Research → TDD → Verify → Handoff]

---

Task 3.2 complete.
✅ Handoff updated
✅ Tests pass
✅ Quality checks pass
✅ Changes committed

---

Invoking ktask for Task 3.3...

/ktask impl: docs/designs/feature/implementation/M3_core.md task: 3.3

[... continues through 3.4 ...]

---

Invoking ktask for Task 3.5 (VALIDATION)...

/ktask impl: docs/designs/feature/implementation/M3_core.md task: 3.5

REMINDER: This is a VALIDATION task. You MUST use the E2E agent workflow:
e2e-test-designer → e2e-test-architect → e2e-tester
Do NOT run bash commands directly from the milestone file.

[ktask uses e2e agents, reports PASS/FAIL]

---

## Milestone Complete: M3 - Core Implementation

**Tasks completed:** 3.1 through 3.5
**Quality gates:** All passed

**Handoff:** docs/designs/feature/implementation/HANDOFF_M3.md

### E2E Tests Performed

| Test | Steps | Result |
|------|-------|--------|
| feature/core-workflow | 6 | ✅ PASSED |

### Challenges & Solutions

| Task | Challenge | Solution |
|------|-----------|----------|
| 3.2 | Import cycle between modules | Moved shared types to separate file |
| 3.4 | Flaky test due to timing | Added retry logic with backoff |

Ready for PR creation.
```
