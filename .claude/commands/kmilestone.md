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

```
/ktask impl: <milestone_file> task: <task_id>
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

#### Step 2d: Compact Context

**Before starting the next task, compact context:**

Tell the user:
```
Task X.Y complete. Before continuing to X.Z, please run /compact to free up context.
```

Wait for user to confirm, then continue to next task.

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
| ❌ Running E2E bash commands manually | Skips e2e-tester agent validation | Let ktask use e2e agents |
| ❌ Skipping handoff verification | Next task loses context | Always verify handoff updated |
| ❌ Continuing without `/compact` | Context bloats, quality degrades | Ask user to `/compact` between tasks |
| ❌ Batching multiple tasks | Loses per-task verification | One ktask invocation per task |

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
| User declines `/compact` | Continue, but warn about context limits |

---

## Quick Reference

| Phase | Action | Output |
|-------|--------|--------|
| **Initialize** | Parse milestone + handoff | "Starting from: X.Y" |
| **Per-task** | `/ktask impl: <file> task: <id>` | ktask completes task |
| **Verify** | Check handoff, tests, quality | All checks pass |
| **Quality check** | unit-test-quality-checker (CODING) | No issues found |
| **Compact** | Ask user to run `/compact` | User confirms |
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

Before continuing to Task 3.3, please run /compact to free up context.

[User runs /compact]

---

Invoking ktask for Task 3.3...

/ktask impl: docs/designs/feature/implementation/M3_core.md task: 3.3

[... continues ...]

---

## Milestone Complete: M3 - Core Implementation

Tasks completed: 3.1 through 3.5
Quality gates: All passed
E2E validation: Passed

Ready for PR creation.
```
