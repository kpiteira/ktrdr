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

#### Step 2c: Run Unit Test Quality Check (CODING tasks only)

For CODING tasks, invoke the quality checker:

```
Task(
    subagent_type="unit-test-quality-checker",
    prompt="Check tests modified in task <task_id>: <list test files>"
)
```

If issues found: fix and re-check (up to 2 retries).

#### Step 2d: Continue to Next Task

Proceed directly to the next task. Do NOT pause to ask for `/compact` between tasks.

If context becomes too large during execution, you may ask the user to run `/compact` at that point.

---

### 3. Complete Milestone

After all tasks complete:

```
## Milestone Complete: M4 - Cleanup

**Tasks completed:** 4.1 through 4.6
**Quality gates:** All passed
**E2E validation:** Passed (final VALIDATION task)

**Handoff:** docs/designs/.../HANDOFF_M4.md

Ready for PR creation.
```

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
| **Quality check** | unit-test-quality-checker (CODING) | No issues found |
| **Complete** | Report summary | Ready for PR |

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

Tasks completed: 3.1 through 3.5
Quality gates: All passed
E2E validation: Passed

Ready for PR creation.
```
