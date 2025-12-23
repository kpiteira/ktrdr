# Design: Orchestrator v2 - Haiku Brain Architecture

## Problem Statement

The current orchestrator suffers from brittleness due to regex-based interpretation:

1. **Plan parsing fails on edge cases** - The regex parser extracts tasks from markdown, but can't distinguish between real tasks and example tasks inside code blocks (e.g., E2E test scenarios that contain sample plan snippets).

2. **Result interpretation is fragile** - Determining whether a task succeeded relies on pattern matching Claude's output, which varies in format and wording.

3. **Loop detection uses arbitrary heuristics** - Hardcoded rules like "3 failures = escalate" don't account for context (e.g., different errors each time vs. same error repeatedly).

4. **Interactive tools don't work** - When sandbox Claude uses `AskUserQuestion`, the orchestrator returns an error instead of surfacing the question to the user.

These issues were discovered during testing when:
- A 2-task milestone was interpreted as 4 tasks (parser found tasks inside E2E code blocks)
- Claude's questions about branch strategy were silently ignored
- PR creation was abandoned mid-way due to turn limits

## Goals

1. **Eliminate brittleness** - No regex parsing, no pattern matching, no hardcoded heuristics
2. **Preserve autonomy** - User can kick off a milestone and walk away
3. **Maintain quality escalation** - When Claude needs help, the user is notified
4. **Keep the good UX** - Streaming output from sandbox must be preserved
5. **Preserve all capabilities** - Model selection, resume, single task, guidance, notifications, history, costs

## Non-Goals

1. **Interactive supervision** - The user should not need to watch the execution
2. **Perfect accuracy** - Some interpretation ambiguity is acceptable; escalation handles edge cases
3. **Minimizing API calls** - Haiku is cheap enough that a few extra calls don't matter

## Solution Overview

Replace all interpretation logic with Claude Haiku API calls. The Python orchestrator becomes thin coordination code while Haiku handles all understanding.

**Current flow (brittle):**
```
Plan file → Regex parser → Tasks
Sandbox output → Regex interpreter → Status
Failure count → Hardcoded rules → Retry/escalate decision
```

**New flow (intelligent):**
```
Plan file → Haiku: "What tasks are in this plan?" → Tasks
Sandbox output → Haiku: "Did this succeed?" → Status
Attempt history → Haiku: "Should we retry or escalate?" → Decision
```

## Key Decisions

### Decision 1: Haiku for orchestration, Opus for execution

**Context:** We need intelligence for interpretation but want to control costs.

**Decision:** Use Claude Haiku for all orchestration decisions (plan parsing, result interpretation, retry logic). Use the user-selected model (defaulting to Opus) for actual task execution in the sandbox.

**Rationale:**
- Haiku costs ~$0.001 per call, making orchestration overhead negligible (~$0.01 per milestone)
- Orchestration tasks (understanding structure, interpreting results) are simpler than coding tasks
- Actual coding work benefits from Opus-level capability
- User can still choose `-m haiku` for cheap test runs

### Decision 2: Stateless orchestration calls

**Context:** Should the Haiku orchestrator maintain conversation context across calls?

**Decision:** Each Haiku call is independent. State is managed in JSON files, not in conversation history.

**Rationale:**
- Avoids context window issues for long milestones
- State files already exist and work well for resume functionality
- Simpler architecture - each call is self-contained
- Relevant history can be included in prompts when needed (e.g., previous attempt summaries for retry decisions)

### Decision 3: Preserve sandbox invocation pattern

**Context:** The current sandbox invocation with streaming works well.

**Decision:** Keep the existing `sandbox.invoke_claude()` pattern that streams tool calls to the terminal.

**Rationale:**
- The streaming UX is valuable for observability during system development
- The invocation mechanism itself isn't brittle - only the interpretation around it
- Changing it would be unnecessary churn

### Decision 4: Merge scattered logic into single runner

**Context:** Current codebase has logic spread across `task_runner.py`, `e2e_runner.py`, `escalation.py`, `loop_detector.py`.

**Decision:** Consolidate into a single `runner.py` with clear phases: task loop, E2E, completion.

**Rationale:**
- The complexity that justified separate modules came from regex/heuristic logic
- With Haiku handling interpretation, the remaining code is simple coordination
- Single file is easier to understand and maintain

### Decision 5: Delete rather than deprecate

**Context:** Should we keep old parsing code as fallback?

**Decision:** Delete `plan_parser.py`, `llm_interpreter.py`, `loop_detector.py` entirely.

**Rationale:**
- Karl explicitly stated willingness to "trash 100% of what we did"
- Keeping old code creates maintenance burden and confusion
- Haiku interpretation is strictly better - no scenario where regex is preferred
- Clean break makes the codebase simpler

## User Experience

### Running a Milestone

```
$ orchestrator run docs/milestones/my-feature.md

Analyzing plan...
Found 3 tasks

Starting task 1.1: Create data model
  → Reading DESIGN.md...
  → Writing models.py...
  → Running: uv run pytest tests/test_models.py...
  → TodoWrite...
Task 1.1: COMPLETED (142s, 45.2k tokens, $0.45)

Starting task 1.2: Add API endpoint
  → Reading models.py...
  → Editing api/routes.py...
  → Running: uv run pytest tests/test_api.py...
Task 1.2: COMPLETED (98s, 32.1k tokens, $0.32)

Starting task 1.3: Update documentation
  → Reading README.md...
  → Editing README.md...
Task 1.3: COMPLETED (34s, 12.4k tokens, $0.12)

Running E2E tests...
  → Running: curl http://localhost:8000/api/v1/...
  → Running: pytest tests/e2e/...
E2E: PASSED (67s)

Milestone COMPLETED
  Tasks: 3/3 completed
  Duration: 5m 41s
  Tokens: 89.7k
  Cost: $0.90
```

### Escalation

When Claude needs help, the user receives a notification (macOS/Slack) and sees:

```
Task 1.2: NEEDS HELP

Claude's assessment:
  "The API endpoint requires authentication, but the plan doesn't specify
   which auth method to use. The codebase has both JWT and API key patterns."

Options:
  A) Use JWT authentication (matches user service)
  B) Use API key authentication (matches external integrations)
  C) Skip authentication for now (add later)

Waiting for input...
Your choice: A

Resuming with guidance: "Use JWT authentication"
```

### Resume After Interruption

```
$ orchestrator resume docs/milestones/my-feature.md

Resuming milestone: my-feature
  Previously completed: 1.1, 1.2
  Continuing from: 1.3

Starting task 1.3: Update documentation
  ...
```

### Model Selection

```
# Fast/cheap testing
$ orchestrator run plan.md -m haiku

# Default (Opus-level quality)
$ orchestrator run plan.md

# Explicit Opus
$ orchestrator run plan.md -m opus
```

### Single Task with Guidance

```
$ orchestrator task plan.md 1.2 -g "Use the new async pattern from PR #123"

Executing task 1.2: Add API endpoint
  Additional guidance: "Use the new async pattern from PR #123"
  → ...
```

## Requirements

### Functional Requirements

1. **Plan Understanding**
   - Extract tasks from milestone plan markdown
   - Handle any reasonable plan format (not dependent on exact heading syntax)
   - Ignore task-like content inside code blocks
   - Extract E2E test scenarios when present

2. **Task Execution**
   - Invoke Claude Code in sandbox with task context
   - Stream tool calls to terminal in real-time
   - Support model selection (haiku/sonnet/opus)
   - Capture full session output for interpretation

3. **Result Interpretation**
   - Determine task status: completed, failed, or needs_help
   - Provide human-readable summary of what happened
   - For needs_help: extract question and options if present

4. **Retry Logic**
   - Automatically retry failed tasks when retry might help
   - Escalate when retrying won't help (same error repeatedly, explicit confusion)
   - Include attempt history in retry decisions

5. **Escalation**
   - Notify user via configured channels (macOS notification, Slack)
   - Present Claude's question/options clearly
   - Wait for user response
   - Resume with user's guidance

6. **State Management**
   - Persist state after each task completion
   - Support resume from any interruption point
   - Track: completed tasks, attempt counts, costs, durations

7. **Observability**
   - Stream sandbox activity to terminal
   - Capture session transcripts for debugging
   - Track tokens and costs per task

### Non-Functional Requirements

1. **Cost Efficiency**
   - Haiku orchestration overhead < $0.05 per milestone
   - No unnecessary API calls

2. **Reliability**
   - Graceful handling of API failures
   - State saved frequently to minimize lost work on crash

3. **Simplicity**
   - Total orchestrator code < 500 lines (excluding tests)
   - Single person should understand entire codebase in < 1 hour

## Capabilities Preserved from v1

| Capability | How Preserved |
|------------|---------------|
| `orchestrator run plan.md` | Main entry point unchanged |
| `orchestrator resume plan.md` | State loading unchanged |
| `orchestrator task plan.md 1.1` | Filter to single task |
| `-m haiku/sonnet/opus` | Pass to sandbox invocation |
| `-g "guidance"` | Append to task prompt |
| `--notify / --no-notify` | Notification system unchanged |
| `orchestrator history` | Reads state JSON files (unchanged) |
| `orchestrator costs` | Reads state JSON files (unchanged) |
| `orchestrator health` | Health check unchanged |
| Streaming tool calls | Sandbox streaming unchanged |

## Constraints

1. **Sandbox Isolation** - All task execution happens in the Docker sandbox. The orchestrator never executes code on the host.

2. **Haiku for Orchestration Only** - Haiku makes decisions but never executes tasks. Task execution always uses the user-selected model in sandbox.

3. **No Interactive Mode** - The orchestrator runs autonomously. User interaction only happens during escalation.

## Open Questions

1. ~~**Haiku prompt optimization** - Should we fine-tune prompts based on observed failures, or keep them simple and general?~~ **RESOLVED:** Start simple, iterate based on observed failures.

2. **Streaming granularity** - Currently streams tool names. Should we stream more (arguments, partial output) or keep it minimal?

3. **PR creation** - Currently handled by asking Claude to create PR. Should this be orchestrator logic instead?

## Validated Decisions (from design validation)

The following decisions were made during design validation:

### Decision 6: No v1 backward compatibility

**Context:** Should v2 support resuming milestones started with v1?

**Decision:** No. Fresh start, delete old code entirely.

**Rationale:** Karl explicitly stated "absolutely not. Let's keep it simple! Anything v1 goes to trash." Maintaining compatibility adds complexity for no practical benefit.

### Decision 7: Task extraction - minimal fields

**Context:** What fields should Haiku extract from tasks?

**Decision:** Extract `{id, title, description}` only. The `/ktask` skill reads detailed fields (file_path, acceptance_criteria) from the plan directly.

**Rationale:** The orchestrator only needs task ID for invoking `/ktask` and title for display. Extracting more fields duplicates what `/ktask` already does.

### Decision 8: No output truncation

**Context:** Should sandbox output be truncated before sending to Haiku for interpretation?

**Decision:** No truncation. Send full output to Haiku.

**Rationale:** Haiku is cheap enough that larger context doesn't matter cost-wise. Truncation risks losing important information (e.g., errors at the end of long output).

### Decision 9: Retry guidance from Haiku

**Context:** When Haiku decides to retry, should it also suggest what to tell Claude differently?

**Decision:** Yes. Include `guidance_for_retry` in the retry decision response.

**Rationale:** Haiku has context about why the attempt failed. Suggesting targeted guidance (e.g., "verify the module is installed first") makes retries more effective than blind re-runs.

### Decision 10: Keep regex for E2E extraction

**Context:** Should E2E scenario extraction use Haiku or keep existing regex?

**Decision:** Keep regex for extraction, use Haiku only for E2E result interpretation.

**Rationale:** E2E sections are structured (`## E2E Test` heading with code blocks). The regex is simple and works. Haiku adds value for interpretation, not extraction.

## Success Criteria

1. The task-parsing bug (finding tasks in code blocks) is eliminated
2. AskUserQuestion from sandbox Claude surfaces to user properly
3. A milestone can run unattended from start to completion (or escalation)
4. Streaming UX is identical or better than v1
5. All existing CLI capabilities work
6. Total Haiku cost overhead < $0.05 per milestone
