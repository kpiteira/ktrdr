# Milestone Execution Command

Executes an entire milestone by running each task through the ktask workflow, with intelligent context compaction between tasks.

This command embodies our partnership values from CLAUDE.md — automation of low-value repetition while preserving human checkpoints where they matter.

---

## Command Usage

```
/kmilestone @<milestone_file.md> [--from <task_id>]
```

**Required:**
- `@milestone_file.md` — The milestone implementation plan (e.g., `@M4_workers.md`)

**Optional:**
- `--from <task_id>` — Start from specific task (default: auto-detect from handoff)

---

## How It Works

kmilestone is a thin orchestration layer. The heavy lifting stays in ktask:

```
kmilestone (orchestration)
    │
    ├── Parse milestone → task list
    ├── Parse handoff → completed tasks
    │
    └── For each remaining task:
            │
            ├── Prepare minimal context
            ├── Execute via ktask workflow (TDD, handoff, gates)
            ├── Run unit test quality check
            ├── Compact context
            └── Continue
```

**ktask is unchanged.** All safeguards (TDD, handoffs, quality gates) remain.

---

## Workflow

### 1. Initialize

1. **Parse milestone file** — Extract ordered task list from `## Task X.Y` headings
2. **Locate handoff file** — Same directory, pattern `HANDOFF_<milestone>.md`
3. **Parse handoff** — Find "Task X.Y Complete" sections → determine completed tasks
4. **Identify next task** — First task not marked complete

**Output to user:**
```
Milestone: M4 - Worker Settings (10 tasks)
Completed: 4.1, 4.2, 4.3 (from handoff)
Resuming from: 4.4
```

If `--from` specified, override the auto-detected start point.

### 2. Task Execution Loop

For each remaining task:

#### 2a. Prepare Context

Set up minimal context for the task:

```markdown
## Current Execution State

**Milestone:** <path to milestone file>
**Handoff:** <path to handoff file>
**Completed tasks:** <list>
**Current task:** <task_id>

---

## Handoff Content

<include full handoff file content here>

---

## Current Task

<include current task content from milestone file>
```

#### 2b. Execute Task

Follow the **complete ktask workflow** for this task:

1. **Setup** — Retrieve task, verify branch, classify type (CODING/VALIDATION/RESEARCH)
2. **Research** — Read context docs, check handoffs, find patterns
3. **Implement** — TDD cycle for CODING tasks, E2E agents for VALIDATION tasks
4. **Verify** — Acceptance criteria, quality gates (`make test-unit`, `make quality`)
5. **Complete** — Update handoff (MANDATORY), commit changes

**On questions:** Use AskUserQuestion — this pauses execution for human input, just like in kdesign commands.

**On failure:** ktask handles fix-and-retry internally. If truly blocked, stop and report.

#### 2c. Unit Test Quality Check (CODING tasks only)

After each CODING task completes, run a quality check on new/modified tests:

```
Task(
    subagent_type="unit-test-quality-checker",
    prompt="""
    ## Unit Test Quality Check Request

    **Task:** <task_id> - <task_name>
    **Test files to check:**
    - <list new/modified test files from this task>

    **Context:** <brief description of what was implemented>
    """
)
```

The agent checks for:
- No docker/compose dependencies
- No real database connections
- No slow sleeps (>1s)
- External dependencies properly mocked
- Meaningful assertions
- No running services required

**If issues found:** Fix them and re-run quality check (up to 2 retries). If still failing, AskUserQuestion.

#### 2d. Compact and Continue

After task completion:

1. **Verify handoff updated** — The task MUST have added a "Task X.Y Complete" section
2. **Compact context** — Clear working memory, preserve only:
   ```
   Milestone: <path>
   Handoff: <path>
   Completed: <updated list including just-finished task>
   Next task: <next task_id>
   ```
3. **Loop** — Continue to next task

### 3. Completion

After all tasks complete:

```
## Milestone Complete: M4 - Worker Settings

**Tasks completed:** 4.1 through 4.10
**Quality gates:** All passed
**E2E validation:** Passed (task 4.10)

**Handoff:** docs/designs/config-system/implementation/HANDOFF_M4.md

Ready for PR creation. Run: gh pr create ...
```

---

## Resume Behavior

kmilestone is **idempotent**. Running it again on the same milestone:

1. Parses handoff file
2. Finds "Task X.Y Complete" sections
3. Resumes from first incomplete task

No special handling needed — just run `/kmilestone @M4_workers.md` again.

**Force restart:** Use `--from 4.1` to ignore handoff and start fresh.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Task fails quality gates | ktask fixes and retries internally |
| Unit test quality issues | Fix and re-check (up to 2 retries) |
| Question arises | AskUserQuestion → pauses for human input |
| Unrecoverable blocker | Stop, report status, await guidance |
| Handoff not updated | Error — task did not complete properly |

---

## What kmilestone Does NOT Change

- **ktask workflow** — Unchanged, all safeguards preserved
- **TDD requirement** — Still mandatory for CODING tasks
- **Handoff creation** — Still mandatory after every task
- **E2E agent usage** — VALIDATION tasks still use e2e-test-designer/architect/tester
- **Quality gates** — `make test-unit` and `make quality` still required

kmilestone automates the low-value "clear context, invoke next task" loop. The high-value parts (TDD, handoffs, human checkpoints via questions) remain.

---

## Example Execution

```
User: /kmilestone @docs/designs/config-system/implementation/M5_api_client.md

Claude:
Milestone: M5 - API Client Settings (6 tasks)
Completed: (none - fresh start)
Starting from: 5.1

---

## Task 5.1: Create APIClientSettings Class

[Executes full ktask workflow...]
[Updates handoff...]
[Runs unit test quality check: PASS]

Task 5.1 complete. Compacting context...

---

## Task 5.2: Add Timeout Configuration

[Executes full ktask workflow...]
[Updates handoff...]
[Runs unit test quality check: PASS]

Task 5.2 complete. Compacting context...

[... continues through all tasks ...]

---

## Milestone Complete: M5 - API Client Settings

Tasks completed: 5.1 through 5.6
Quality gates: All passed
E2E validation: Passed

Ready for PR creation.
```

---

## Quick Reference

| Phase | What Happens |
|-------|--------------|
| Initialize | Parse milestone + handoff, find resume point |
| Per-task | ktask workflow (TDD, implement, handoff, gates) |
| Quality check | Validate unit tests aren't integration tests |
| Compact | Clear context, preserve paths + completion state |
| Complete | Report summary, ready for PR |
