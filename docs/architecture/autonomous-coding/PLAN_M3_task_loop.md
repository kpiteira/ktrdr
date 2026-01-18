---
design: docs/architecture/autonomous-coding/DESIGN.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE.md
---

# Milestone 3: Task Loop + State + Resume

**Branch:** `feature/orchestrator-m3-task-loop`
**Builds on:** M2 (single task works)
**Estimated Tasks:** 9

---

## Capability

Orchestrator runs all tasks in a milestone sequentially, persists state after each task, displays Claude's task summary for visibility, and can resume from where it left off after interruption.

**Note:** Git operations (branch, commit, PR) are handled by Claude via `/ktask`, not by the orchestrator. The orchestrator prompts for PR creation at milestone end, then tells Claude to create it.

---

## E2E Test Scenario

```bash
# 1. Run the 3-task health_check milestone
uv run orchestrator run orchestrator/test_plans/health_check.md

# Expected output:
# [14:23:01] Starting milestone: Orchestrator Health Check
# [14:23:01] Task 1.1: Create health module
#            Invoking Claude Code...
#            → Reading orchestrator/config.py...
#            → Writing orchestrator/health.py...
#            → Writing orchestrator/tests/test_health.py...
#            → Running tests...
# [14:23:45] Task 1.1: COMPLETED (44s, 4.2k tokens, $0.03)
#
#            ## Task Complete: 1.1
#            **What was implemented:**
#            - Created health.py module with system health checks
#            **Files changed:**
#            - orchestrator/health.py (created)
#            - orchestrator/tests/test_health.py (created)
#            **Key decisions made:**
#            - Used psutil for system metrics
#            **Issues encountered:**
#            - None
#
# [14:23:46] Task 1.2: Add health CLI command
#            Invoking Claude Code...
# [14:24:18] Task 1.2: COMPLETED (32s, 3.1k tokens, $0.02)
#            [Task summary displayed...]
# [14:24:19] Task 1.3: Add health telemetry
#            Invoking Claude Code...
# [14:24:51] Task 1.3: COMPLETED (32s, 2.9k tokens, $0.02)
#            [Task summary displayed...]
#
# All tasks complete!
# Summary:
#   Tasks: 3/3 completed
#   Duration: 1m 54s
#   Tokens: 10.2k
#   Cost: $0.07
#
# Create PR for this milestone? [Y/n]: y
# [Invoking Claude to create PR...]
# PR created: https://github.com/user/ktrdr/pull/123

# 2. Verify state file
cat state/health_check_state.json | jq '{completed: .completed_tasks, status: .e2e_status}'
# Expect: {"completed": ["1.1", "1.2", "1.3"], "status": null}

# 3. Review and test the PR
gh pr checkout 123
uv run pytest orchestrator/tests/
# Verify the health module works, then merge or request changes

# 4. Test resume (simulate interruption)
# Start milestone, Ctrl+C after task 1
uv run orchestrator run orchestrator/test_plans/health_check.md
# ^C during task 1.2

# Check state
cat state/health_check_state.json | jq '.completed_tasks'
# Expect: ["1.1"]

# Resume
uv run orchestrator resume orchestrator/test_plans/health_check.md
# Expect: "Resuming from Task 1.2..."
# Should complete tasks 1.2 and 1.3, then prompt for PR

# 5. Verify trace hierarchy in Jaeger
open http://localhost:16686
# Search service=orchestrator
# Expect: orchestrator.milestone span containing 3 orchestrator.task child spans

# 6. Verify concurrent run protection
# Terminal 1:
uv run orchestrator run orchestrator/test_plans/health_check.md &
# Terminal 2 (immediately):
uv run orchestrator run orchestrator/test_plans/health_check.md
# Expect: "Error: Milestone already running (PID: xxxxx)"
```

---

## Tasks

### Task 3.1: Create State Manager

**File:** `orchestrator/state.py`
**Type:** CODING

**Description:**
Persist orchestrator state for resumability.

**Implementation Notes:**

```python
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import json

@dataclass
class OrchestratorState:
    milestone_id: str
    plan_path: str
    started_at: datetime
    current_task_index: int = 0
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    task_results: dict[str, dict] = field(default_factory=dict)  # TaskResult as dict
    e2e_status: str | None = None

    # Loop detection state (for M4)
    task_attempt_counts: dict[str, int] = field(default_factory=dict)
    task_errors: dict[str, list[str]] = field(default_factory=dict)
    e2e_attempt_count: int = 0
    e2e_errors: list[str] = field(default_factory=list)

    def save(self, state_dir: Path) -> None:
        """Persist to JSON file."""
        state_dir.mkdir(exist_ok=True)
        path = state_dir / f"{self.milestone_id}_state.json"

        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, state_dir: Path, milestone_id: str) -> "OrchestratorState | None":
        """Load from JSON file if exists."""
        path = state_dir / f"{milestone_id}_state.json"
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        data["started_at"] = datetime.fromisoformat(data["started_at"])
        return cls(**data)

    def mark_task_completed(self, task_id: str, result: "TaskResult") -> None:
        """Mark a task as completed and save."""
        self.completed_tasks.append(task_id)
        self.task_results[task_id] = asdict(result)
        self.current_task_index += 1

    def get_next_task_index(self) -> int:
        """Get index of next task to run."""
        return len(self.completed_tasks)
```

**Acceptance Criteria:**

- [ ] State saves to JSON file
- [ ] State loads from JSON file
- [ ] Handles datetime serialization
- [ ] State directory created if not exists
- [ ] Unit tests for save/load cycle

---

### Task 3.2: Create Lock Manager

**File:** `orchestrator/lock.py`
**Type:** CODING

**Description:**
Simple PID-based lock to prevent concurrent runs on same milestone.

**Implementation Notes:**

```python
from pathlib import Path
import os

class MilestoneLock:
    def __init__(self, state_dir: Path, milestone_id: str):
        self.lock_path = state_dir / f"{milestone_id}.lock"

    def acquire(self) -> bool:
        """Try to acquire lock. Returns False if already held."""
        if self.lock_path.exists():
            # Check if PID is still running
            try:
                pid = int(self.lock_path.read_text().strip())
                os.kill(pid, 0)  # Check if process exists
                return False  # Lock held by running process
            except (ProcessLookupError, ValueError):
                pass  # Stale lock, can acquire

        # Acquire lock
        self.lock_path.write_text(str(os.getpid()))
        return True

    def release(self) -> None:
        """Release the lock."""
        if self.lock_path.exists():
            self.lock_path.unlink()

    def __enter__(self):
        if not self.acquire():
            pid = self.lock_path.read_text().strip()
            raise RuntimeError(f"Milestone already running (PID: {pid})")
        return self

    def __exit__(self, *args):
        self.release()
```

**Acceptance Criteria:**

- [ ] Lock acquired with PID
- [ ] Lock detected when process running
- [ ] Stale lock (dead PID) can be acquired
- [ ] Context manager works
- [ ] Unit tests cover scenarios

---

### Task 3.3: Create Milestone Runner

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
Run all tasks in a milestone sequentially with state persistence.

**Implementation Notes:**

```python
from opentelemetry import trace

async def run_milestone(
    plan_path: str,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
    resume: bool = False,
) -> MilestoneResult:
    """Run all tasks in a milestone."""

    # Parse plan
    milestone_id = Path(plan_path).stem
    tasks = parse_plan(plan_path)

    # Load or create state
    state = OrchestratorState.load(config.state_dir, milestone_id)
    if state is None or not resume:
        state = OrchestratorState(
            milestone_id=milestone_id,
            plan_path=plan_path,
            started_at=datetime.now(),
        )

    sandbox = CodingAgentContainer()
    start_index = state.get_next_task_index()

    with tracer.start_as_current_span("orchestrator.milestone") as milestone_span:
        milestone_span.set_attribute("milestone.id", milestone_id)
        milestone_span.set_attribute("milestone.total_tasks", len(tasks))
        milestone_span.set_attribute("milestone.resume", resume)

        console.print(f"[bold]Starting milestone:[/bold] {milestone_id}")
        if resume and start_index > 0:
            console.print(f"Resuming from Task {tasks[start_index].id}...")

        total_cost = 0.0
        total_tokens = 0

        for i, task in enumerate(tasks[start_index:], start=start_index):
            with tracer.start_as_current_span("orchestrator.task") as task_span:
                task_span.set_attribute("task.id", task.id)

                console.print(f"[bold]Task {task.id}:[/bold] {task.title}")
                console.print("Invoking Claude Code...")

                result = await run_task(task, sandbox, config)

                # Record telemetry
                task_span.set_attribute("task.status", result.status)
                task_span.set_attribute("claude.tokens", result.tokens_used)
                task_span.set_attribute("claude.cost_usd", result.cost_usd)

                tasks_counter.add(1, {"milestone": milestone_id, "status": result.status})
                tokens_counter.add(result.tokens_used, {"milestone": milestone_id})
                cost_counter.add(result.cost_usd, {"milestone": milestone_id})
                task_duration.record(result.duration_seconds, {"milestone": milestone_id})

                total_cost += result.cost_usd
                total_tokens += result.tokens_used

                # Handle result
                if result.status == "completed":
                    state.mark_task_completed(task.id, result)
                    state.save(config.state_dir)

                    console.print(
                        f"Task {task.id}: [bold green]COMPLETED[/bold] "
                        f"({result.duration_seconds:.0f}s, {result.tokens_used/1000:.1f}k tokens, ${result.cost_usd:.2f})"
                    )

                elif result.status == "needs_human":
                    # Save state, will be handled by M4
                    state.save(config.state_dir)
                    console.print(f"Task {task.id}: [bold yellow]NEEDS HUMAN[/bold]")
                    return MilestoneResult(status="needs_human", state=state)

                elif result.status == "failed":
                    state.failed_tasks.append(task.id)
                    state.save(config.state_dir)
                    console.print(f"Task {task.id}: [bold red]FAILED[/bold]")
                    console.print(f"Error: {result.error}")
                    return MilestoneResult(status="failed", state=state)

        # All tasks complete
        milestone_span.set_attribute("milestone.total_cost_usd", total_cost)
        milestone_span.set_attribute("milestone.total_tokens", total_tokens)
        milestone_span.set_attribute("milestone.tasks_completed", len(state.completed_tasks))

        console.print(f"\n[bold green]Milestone complete:[/bold] {len(state.completed_tasks)}/{len(tasks)} tasks")
        console.print(f"  Duration: {format_duration(total_duration)}")
        console.print(f"  Tokens: {total_tokens/1000:.1f}k")
        console.print(f"  Cost: ${total_cost:.2f}")

        return MilestoneResult(status="completed", state=state)
```

**Acceptance Criteria:**

- [ ] Runs all tasks sequentially
- [ ] Saves state after each task
- [ ] Supports resume from last completed
- [ ] Creates milestone parent span
- [ ] Handles needs_human and failed statuses
- [ ] Outputs progress and summary

---

### Task 3.4: Add Run Command to CLI

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator run` command for full milestone execution.

**Implementation Notes:**

```python
@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--notify/--no-notify", default=False, help="Send macOS notifications")
def run(plan_file: str, notify: bool):
    """Run all tasks in a milestone."""
    asyncio.run(_run_milestone(plan_file, resume=False, notify=notify))

async def _run_milestone(plan_file: str, resume: bool, notify: bool):
    config = OrchestratorConfig.from_env()
    tracer, meter = setup_telemetry(config)
    create_metrics(meter)

    milestone_id = Path(plan_file).stem

    # Acquire lock
    lock = MilestoneLock(config.state_dir, milestone_id)

    with lock:
        result = await run_milestone(plan_file, config, tracer, resume=resume)

        if notify:
            send_notification(
                title=f"Milestone {result.status}",
                message=f"{milestone_id}: {len(result.state.completed_tasks)} tasks completed"
            )

        return result
```

**Acceptance Criteria:**

- [ ] `orchestrator run <plan>` executes milestone
- [ ] Lock prevents concurrent runs
- [ ] --notify flag triggers macOS notification
- [ ] Outputs progress during execution

---

### Task 3.5: Add Resume Command to CLI

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator resume` command to continue from saved state.

**Implementation Notes:**

```python
@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--notify/--no-notify", default=False)
def resume(plan_file: str, notify: bool):
    """Resume a previously interrupted milestone."""
    config = OrchestratorConfig.from_env()
    milestone_id = Path(plan_file).stem

    # Check state exists
    state = OrchestratorState.load(config.state_dir, milestone_id)
    if state is None:
        console.print(f"[red]No saved state for {milestone_id}[/red]")
        console.print("Use 'orchestrator run' to start a new run.")
        return

    if len(state.completed_tasks) == 0:
        console.print(f"[yellow]No tasks completed yet. Use 'orchestrator run' instead.[/yellow]")
        return

    console.print(f"Found state: {len(state.completed_tasks)} tasks completed")

    asyncio.run(_run_milestone(plan_file, resume=True, notify=notify))
```

**Acceptance Criteria:**

- [ ] `orchestrator resume <plan>` works
- [ ] Errors if no state exists
- [ ] Continues from last completed task
- [ ] Shows how many tasks already done

---

### Task 3.6: Add Task Duration Histogram

**File:** `orchestrator/telemetry.py`
**Type:** CODING

**Description:**
Add histogram metric for task duration distribution.

**Implementation Notes:**

```python
task_duration: metrics.Histogram

def create_metrics(meter: metrics.Meter):
    global tasks_counter, tokens_counter, cost_counter, task_duration

    # ... existing counters ...

    task_duration = meter.create_histogram(
        "orchestrator_task_duration_seconds",
        description="Task execution duration",
        unit="s",
    )
```

**Acceptance Criteria:**

- [ ] Histogram records task durations
- [ ] Queryable in Prometheus
- [ ] Can compute P50/P95/P99

---

### Task 3.7: Add macOS Notification Helper

**File:** `orchestrator/notifications.py`
**Type:** CODING

**Description:**
Send macOS notifications for milestone events.

**Implementation Notes:**

```python
import subprocess
import platform

def send_notification(title: str, message: str, sound: bool = True) -> None:
    """Send macOS notification."""
    if platform.system() != "Darwin":
        return  # Only works on macOS

    script = f'''
    display notification "{message}" with title "{title}"
    '''
    if sound:
        script += ' sound name "default"'

    subprocess.run(["osascript", "-e", script], check=False)
```

**Acceptance Criteria:**

- [ ] Notification appears on macOS
- [ ] Gracefully no-ops on other platforms
- [ ] Sound is optional

---

### Task 3.8: Display Task Summary + Milestone PR Prompt

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
After each task completes, display Claude's task summary to the human for visibility into what happened in the sandbox. At milestone end, prompt the human to create a PR and relay the answer to Claude.

**Implementation Notes:**

```python
# In milestone_runner.py

async def run_milestone(...) -> MilestoneResult:
    # ... existing task loop ...

    for task in tasks[start_index:]:
        result = await run_task(task, sandbox, config)

        if result.status == "completed":
            state.mark_task_completed(task.id, result)
            state.save(config.state_dir)

            # Display task status
            console.print(
                f"Task {task.id}: [bold green]COMPLETED[/bold] "
                f"({result.duration_seconds:.0f}s, {result.tokens_used/1000:.1f}k tokens, ${result.cost_usd:.2f})"
            )

            # Display Claude's task summary for visibility
            console.print(f"\n{result.output}\n")  # Claude's final message includes task summary

    # All tasks complete - prompt for PR
    console.print(f"\n[bold green]All tasks complete![/bold]")
    console.print(f"  Tasks: {len(state.completed_tasks)}/{len(tasks)}")
    console.print(f"  Cost: ${total_cost:.2f}")

    if click.confirm("Create PR for this milestone?", default=True):
        # Tell Claude to create the PR for the whole milestone
        pr_prompt = f"""Create a PR for milestone {milestone_id}.

Completed tasks: {', '.join(state.completed_tasks)}
Total cost: ${total_cost:.2f}

Use `gh pr create` with a summary of all changes made across the tasks."""

        pr_result = await sandbox.invoke_claude(pr_prompt, max_turns=10)
        # Extract PR URL from output (Claude will output it)
        console.print(pr_result.output)

    return MilestoneResult(status="completed", state=state)
```

**Acceptance Criteria:**

- [ ] Claude's task summary displayed after each task completes
- [ ] Human can see what files changed, decisions made, issues encountered
- [ ] At milestone end, prompts "Create PR for this milestone?"
- [ ] If yes, invokes Claude to create the PR
- [ ] Claude creates PR with summary of all tasks

---

### Task 3.9: Stream Claude's Progress During Execution

**File:** `orchestrator/sandbox.py`, `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
Stream Claude's tool calls in real-time so the user can see what's happening during execution. Without this, long-running tasks show no output for minutes, making it impossible to know if progress is being made.

**Implementation Notes:**

```python
# In sandbox.py - parse streaming output from claude CLI

async def invoke_claude_streaming(
    prompt: str,
    config: OrchestratorConfig,
    on_tool_call: Callable[[str], None],
) -> TaskResult:
    """Invoke Claude with streaming progress output.

    Args:
        on_tool_call: Callback for each tool call (e.g., "Reading file.py", "Writing test.py")
    """
    # Use --output-format stream-json for claude CLI
    # Parse tool_use events from the stream
    # Call on_tool_call for each tool invocation

    # Example stream events to parse:
    # {"type": "tool_use", "name": "Read", "input": {"file_path": "..."}}
    # {"type": "tool_use", "name": "Write", "input": {"file_path": "..."}}
    # {"type": "tool_use", "name": "Bash", "input": {"command": "pytest ..."}}


# In milestone_runner.py - display progress

def _format_tool_call(tool_name: str, tool_input: dict) -> str:
    """Format tool call for display."""
    if tool_name == "Read":
        return f"→ Reading {Path(tool_input['file_path']).name}..."
    elif tool_name == "Write":
        return f"→ Writing {Path(tool_input['file_path']).name}..."
    elif tool_name == "Edit":
        return f"→ Editing {Path(tool_input['file_path']).name}..."
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")[:50]
        return f"→ Running: {cmd}..."
    elif tool_name == "Grep":
        return f"→ Searching for {tool_input.get('pattern', '')}..."
    else:
        return f"→ {tool_name}..."

async def run_milestone(...):
    for task in tasks:
        console.print(f"[bold]Task {task.id}:[/bold] {task.title}")
        console.print("Invoking Claude Code...")

        def on_progress(tool_name: str, tool_input: dict):
            msg = _format_tool_call(tool_name, tool_input)
            console.print(f"           {msg}")

        result = await sandbox.invoke_claude_streaming(
            prompt=task.prompt,
            config=config,
            on_tool_call=on_progress,
        )
```

**Acceptance Criteria:**

- [ ] User sees tool calls in real-time during task execution
- [ ] File reads/writes show the filename
- [ ] Bash commands show first 50 chars of command
- [ ] Progress updates don't spam (one line per tool call)
- [ ] Works with --output-format stream-json from Claude CLI
- [ ] Falls back gracefully if streaming not available

---

## Milestone Verification

**Full E2E with health_check milestone:**

```bash
# Reset sandbox
./scripts/sandbox-reset.sh

# Run full milestone
uv run orchestrator run orchestrator/test_plans/health_check.md --notify

# Verify task summaries were displayed after each task
# (visual verification during run)

# Verify all 3 tasks completed
cat state/health_check_state.json | jq '.completed_tasks'
# Expect: ["1.1", "1.2", "1.3"]

# Verify PR prompt appeared and PR was created (if answered yes)
gh pr list --state open
# Expect: PR with summary of health_check milestone

# Checkout and test the branch locally
gh pr checkout <pr-number>
uv run pytest orchestrator/tests/
# Verify the health module works as expected

# Verify trace hierarchy
open http://localhost:16686
# Search service=orchestrator
# Expect: orchestrator.milestone span with 3 child task spans

# Test resume flow
./scripts/sandbox-reset.sh  # Reset workspace
rm state/health_check_state.json  # Clear state

# Start and interrupt
timeout 60 uv run orchestrator run orchestrator/test_plans/health_check.md || true
# Should complete ~1 task

# Resume
uv run orchestrator resume orchestrator/test_plans/health_check.md
# Should complete remaining tasks, then prompt for PR
```

**Checklist:**

- [ ] All tasks complete
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/`
- [ ] E2E test passes: health_check.md runs to completion
- [ ] **Live progress shown during execution** (tool calls streamed)
- [ ] Task summaries displayed after each task (files changed, decisions, issues)
- [ ] PR prompt appears at milestone end
- [ ] PR created via Claude when confirmed
- [ ] Resume works after interruption
- [ ] Lock prevents concurrent runs
- [ ] Trace hierarchy visible in Jaeger
- [ ] Quality gates pass: `make quality`
