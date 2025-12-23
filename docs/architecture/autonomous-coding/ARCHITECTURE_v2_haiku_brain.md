# Orchestrator v2: Architecture

## Overview

The v2 orchestrator replaces brittle regex-based interpretation with Claude Haiku API calls. The Python orchestrator becomes thin coordination code (~350 lines) while Haiku handles all understanding: plan parsing, result interpretation, and retry decisions.

The architecture has three layers:
1. **CLI Layer** — Entry points, argument parsing, UX formatting
2. **Orchestration Layer** — Haiku-powered intelligence for all decisions
3. **Execution Layer** — Sandbox invocation with streaming (unchanged from v1)

## Components

### Haiku Brain

**Responsibility:** All interpretation and decision-making via Claude Code CLI with Haiku model

**Location:** `orchestrator/haiku_brain.py`

**Dependencies:** Claude Code CLI (installed locally)

**Capabilities:**
- Extract tasks from plan markdown (ignoring code blocks)
- Interpret task execution results (completed/failed/needs_help)
- Decide retry vs. escalate based on attempt history
- Interpret E2E results (reuses result interpretation)

**Note:** E2E scenario extraction keeps the existing regex (simple, works). Only interpretation uses Haiku.

**Why a separate component:** Centralizes all Haiku prompts in one place. Makes it easy to tune prompts, add logging, or swap models.

#### Interface Contract

```python
@dataclass
class ExtractedTask:
    id: str           # e.g., "1.1", "2.3"
    title: str        # Task title
    description: str  # Brief description

@dataclass
class InterpretationResult:
    status: Literal["completed", "failed", "needs_help"]
    summary: str
    error: str | None
    question: str | None
    options: list[str] | None
    recommendation: str | None

@dataclass
class RetryDecision:
    decision: Literal["retry", "escalate"]
    reason: str
    guidance_for_retry: str | None  # Suggestion for next attempt


class HaikuBrain:
    """All orchestration intelligence via Claude Haiku."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.model = model

    def extract_tasks(self, plan_content: str) -> list[ExtractedTask]:
        """Extract executable tasks from a milestone plan.
        Ignores tasks inside code blocks, example sections, etc.
        """

    def interpret_result(self, output: str) -> InterpretationResult:
        """Interpret Claude Code output to determine task status.
        No truncation - full output is sent to Haiku.
        """

    def should_retry_or_escalate(
        self,
        task_id: str,
        task_title: str,
        attempt_history: list[str],
        attempt_count: int,
    ) -> RetryDecision:
        """Decide whether to retry a failed task or escalate to human.
        Returns guidance_for_retry when retrying to help next attempt.
        """
```

---

### Runner

**Responsibility:** Main execution loop coordinating tasks, E2E, and state

**Location:** `orchestrator/runner.py`

**Dependencies:** Haiku Brain, Sandbox, State, Notifications

**Phases:**
1. Load plan and extract tasks via Haiku
2. For each task: execute in sandbox, interpret result, handle status
3. Run E2E tests if present
4. Report completion or escalation

**Why merged:** With Haiku handling interpretation, the logic is simple enough for one module. Reduces indirection and makes flow easy to follow.

---

### Sandbox Manager

**Responsibility:** Invoke Claude Code in Docker container with streaming

**Location:** `orchestrator/sandbox.py`

**Dependencies:** Docker, subprocess

**Unchanged from v1:** The sandbox invocation pattern works well. Only the interpretation of results changes.

**Key behaviors:**
- Streams tool calls to callback for UX
- Captures full output for Haiku interpretation
- Supports model selection
- Handles timeout and interruption

---

### State Manager

**Responsibility:** Persist milestone progress for resume capability

**Location:** `orchestrator/state.py`

**Dependencies:** JSON file system

**Unchanged from v1:** State format is backward compatible. New orchestrator can resume v1 milestones.

---

### CLI

**Responsibility:** Entry points, argument parsing, UX output

**Location:** `orchestrator/cli.py`

**Dependencies:** Click, Rich

**Commands:**
- `run` — Execute milestone
- `resume` — Continue interrupted milestone
- `task` — Execute single task
- `history` — Show past runs
- `costs` — Show cost summary
- `health` — Check system status

---

### Notifications

**Responsibility:** Alert user on escalation

**Location:** `orchestrator/notifications.py`

**Dependencies:** macOS osascript, optional Slack webhook

**Unchanged from v1:** Notification mechanism doesn't need changes.

## Data Flow

### Normal Execution Flow

```
User runs: orchestrator run plan.md -m opus
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                         CLI                                  │
│  • Parse arguments                                          │
│  • Load plan file content                                   │
│  • Initialize components                                    │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Haiku Brain                               │
│  • "Extract tasks from this plan"                           │
│  • Returns: [{id: "1.1", title: "...", ...}, ...]          │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Runner                                  │
│  For each task:                                             │
│    1. Print "Starting task X.Y: Title"                      │
│    2. Invoke sandbox (streams to terminal)                  │
│    3. Ask Haiku to interpret result                         │
│    4. If completed → save state, continue                   │
│    5. If failed → ask Haiku retry/escalate                  │
│    6. If needs_help → escalate                              │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Sandbox                                  │
│  • docker exec ... claude --print "..."                     │
│  • Streams tool calls via callback                          │
│  • Returns full output when complete                        │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Haiku Brain                               │
│  • "Did this task succeed?"                                 │
│  • Returns: {status, summary, question?, options?}          │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
            (Loop continues until all tasks done)
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    E2E Phase                                 │
│  • Haiku extracts E2E scenario                              │
│  • Sandbox executes E2E                                     │
│  • Haiku interprets E2E result                              │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
               Completion Summary
```

### Escalation Flow

```
Task execution returns ambiguous/stuck output
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Haiku Brain                               │
│  • Interprets as needs_help                                 │
│  • Extracts: question, options, recommendation              │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   Notifications                              │
│  • macOS notification: "Orchestrator needs input"           │
│  • Optional: Slack message with details                     │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Terminal                                │
│  • Display question and options                             │
│  • Wait for user input                                      │
│  • User selects option or provides guidance                 │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                       Runner                                 │
│  • Resume task with user guidance appended to prompt        │
└─────────────────────────────────────────────────────────────┘
```

### Resume Flow

```
User runs: orchestrator resume plan.md
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      State                                   │
│  • Load state/milestone_state.json                          │
│  • Find completed_tasks: ["1.1", "1.2"]                     │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Haiku Brain                               │
│  • Extract all tasks from plan                              │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Runner                                  │
│  • Skip tasks in completed_tasks                            │
│  • Continue from first incomplete task                      │
└─────────────────────────────────────────────────────────────┘
```

## State Management

### Milestone State

**Location:** `state/{milestone_id}_state.json`

**Shape:**
```
{
  "milestone_id": "PLAN_M1",
  "plan_path": "docs/milestones/feature.md",
  "started_at": "2025-01-15T10:30:00",
  "starting_branch": "main",
  "completed_tasks": ["1.1", "1.2"],
  "failed_tasks": [],
  "task_results": {
    "1.1": {
      "status": "completed",
      "duration_seconds": 142.5,
      "tokens_used": 45200,
      "cost_usd": 0.45,
      "summary": "Created data model with tests"
    }
  },
  "e2e_status": null,
  "attempt_history": {
    "1.2": ["First attempt failed: import error", "Second attempt: fixed import"]
  }
}
```

**Transitions:**
- Created when milestone starts
- Updated after each task completes or fails
- Updated after E2E completes
- Read on resume to determine starting point

**Note:** No v1 backward compatibility. Fresh start - old state files can be deleted.

## Error Handling

### Claude Code CLI Failures (Haiku calls)

**When:** Claude Code CLI returns error (rate limit, server error, network issue)

**Response:** Retry with exponential backoff (3 attempts, similar to existing patterns). If persistent, save state and exit with error message.

**User experience:** "Haiku interpretation failed: {details}. State saved. Resume with: orchestrator resume plan.md"

**Note:** Claude occasionally has transient issues (minutes to tens of minutes). The backoff handles this gracefully.

---

### Sandbox Invocation Failures

**When:** Docker not running, container missing, timeout

**Response:** Save state, notify user, exit

**User experience:** "Sandbox error: {details}. State saved at task {X.Y}."

---

### Task Interpretation Ambiguity

**When:** Haiku returns "unclear" or can't determine status

**Response:** Treat as needs_help, escalate to user

**User experience:** "Task {X.Y} result unclear. Please review output and advise."

---

### Stuck in Retry Loop

**When:** Same error multiple times

**Response:** Haiku's retry/escalate logic detects repeated failures and recommends escalation

**User experience:** "Task {X.Y} has failed 3 times with similar errors. Escalating."

## Integration Points

### Claude Code CLI (Haiku)

**Purpose:** All interpretation and decision-making

**Configuration:** Claude Code must be installed and authenticated locally

**Invocation pattern (from existing llm_interpreter.py):**
```
claude --model claude-haiku-4-5-20251001 \
       --print \
       --no-session-persistence \
       --allowedTools "" \
       -p "{prompt}"
```

Key flags:
- `--allowedTools ""` disables all tools/MCPs for simple Q&A
- `--no-session-persistence` keeps calls stateless
- `--print` returns output directly

**Model:** `claude-haiku-4-5-20251001` for orchestration, user-selected for sandbox execution

---

### Docker / Sandbox Container

**Purpose:** Isolated execution environment for Claude Code

**Configuration:** `SANDBOX_CONTAINER` config (default: `ktrdr-sandbox`)

**Invocation:** `docker exec {container} claude --print "{prompt}" --model {model}`

---

### macOS Notifications

**Purpose:** Alert user on escalation

**Configuration:** Enabled by default, disable with `--no-notify`

**Implementation:** osascript display notification

## Implementation Plan

No v1 backward compatibility - this is a clean replacement.

### Milestones

#### Milestone 1: Haiku Brain + Plan Parsing

- Create `haiku_brain.py` with `extract_tasks()`
- Wire to runner (replace `parse_plan()` call)
- Delete `plan_parser.py`
- E2E test: Plan with tasks in code blocks → correct task count

#### Milestone 2: Result Interpretation via Haiku

- Add `interpret_result()` to HaikuBrain (no truncation)
- Replace hybrid regex+LLM in task_runner.py
- Delete `llm_interpreter.py`
- E2E test: Task completes without STATUS marker → detected as completed

#### Milestone 3: Retry/Escalate via Haiku

- Add `should_retry_or_escalate()` to HaikuBrain
- Wire to runner's retry loop with `guidance_for_retry`
- Delete `loop_detector.py`
- E2E test: Same error 3x → escalation triggered

#### Milestone 4: Consolidated Runner

- Merge task_runner.py, e2e_runner.py, escalation.py into runner.py
- Clean up CLI imports
- Delete deprecated files
- E2E test: Full milestone runs to completion

## File Changes Summary

### Create

| File | Lines (est.) | Purpose |
|------|--------------|---------|
| `orchestrator/haiku_brain.py` | ~150 | Haiku API wrapper with prompts |

### Modify

| File | Change | Lines (est.) |
|------|--------|--------------|
| `orchestrator/runner.py` | Rewrite to use Haiku Brain | ~200 |
| `orchestrator/cli.py` | Simplify imports | ~150 |

### Delete

No quarantine - delete directly as each milestone completes:

| File | Milestone | Reason |
|------|-----------|--------|
| `orchestrator/plan_parser.py` | M1 | Replaced by HaikuBrain.extract_tasks() |
| `orchestrator/llm_interpreter.py` | M2 | Replaced by HaikuBrain.interpret_result() |
| `orchestrator/loop_detector.py` | M3 | Replaced by HaikuBrain.should_retry_or_escalate() |
| `orchestrator/task_runner.py` | M4 | Merged into runner.py |
| `orchestrator/e2e_runner.py` | M4 | Merged into runner.py |
| `orchestrator/escalation.py` | M4 | Merged into runner.py |

**Note:** The CLI invocation pattern from `llm_interpreter.py` is reused in `haiku_brain.py`.

### Keep Unchanged

| File | Reason |
|------|--------|
| `orchestrator/sandbox.py` | Works well, just wire to new runner |
| `orchestrator/state.py` | State management unchanged |
| `orchestrator/config.py` | Configuration unchanged |
| `orchestrator/notifications.py` | Notification mechanism unchanged |
| `orchestrator/models.py` | Data models still useful |
| `orchestrator/telemetry.py` | Telemetry unchanged |

## Appendix: Haiku Prompts

The following prompts were validated during design validation.

### Prompt 1: Extract Tasks

```text
You are parsing a milestone plan to extract tasks for an orchestrator to execute.

CRITICAL: Only extract REAL tasks that should be executed. Ignore:
- Tasks mentioned inside fenced code blocks (```...```)
- Tasks in "Example" or "E2E Test" sections that are illustrative, not actionable
- Duplicate mentions of the same task

Return a JSON array of tasks. Each task has:
- id: The task number (e.g., "1.1", "2.3")
- title: The task title
- description: Brief description of what to implement

Example output:
[
  {"id": "1.1", "title": "Create data model", "description": "..."},
  {"id": "1.2", "title": "Add API endpoint", "description": "..."}
]

Return ONLY the JSON array, no other text.

Plan content:
{plan_content}
```

### Prompt 2: Interpret Result

```text
Analyze this Claude Code output and determine the task status.

Return a JSON object:
{
  "status": "completed" | "failed" | "needs_help",
  "summary": "Brief description of what happened",
  "error": "Error details if failed, null otherwise",
  "question": "The question Claude is asking, if needs_help",
  "options": ["Option A", "Option B"] or null,
  "recommendation": "Claude's recommended option, if stated"
}

Determine status as:
- "completed": Task finished successfully. Look for task summaries, passing tests, successful commits.
- "failed": Task encountered an error it couldn't recover from. Look for unresolved errors, failed tests that weren't fixed, explicit failure messages.
- "needs_help": Claude is asking a question or needs human decision. Look for:
  - AskUserQuestion tool usage
  - Questions like "Which approach should I take?"
  - Statements like "I need clarification" or "I'm blocked"
  - Multiple options presented for human to choose

When in doubt between "completed" and "needs_help", prefer "needs_help" — it's safer to ask than to assume.

Return ONLY the JSON, no other text.

Claude Code output:
{output}
```

### Prompt 3: Retry or Escalate

```text
You are deciding whether to retry a failed task or escalate to a human.

Task: {task_id} - {task_title}

Attempt history:
{attempt_history}

Current attempt count: {attempt_count}

Decide: Should we retry or escalate?

RETRY when:
- The error is different from previous attempts (making progress)
- The error seems transient or fixable (import errors, typos, missing files)
- Only 1-2 attempts so far and the errors aren't identical

ESCALATE when:
- Same or very similar error 3+ times (stuck in a loop)
- The error indicates a design/architecture issue, not a coding bug
- Claude explicitly said it needs human input or is confused
- The error is about something Claude can't fix (permissions, external service, missing context)

Return a JSON object:
{
  "decision": "retry" | "escalate",
  "reason": "Brief explanation of why",
  "guidance_for_retry": "If retrying, what to tell Claude differently (null if escalating)"
}

Return ONLY the JSON, no other text.
```
