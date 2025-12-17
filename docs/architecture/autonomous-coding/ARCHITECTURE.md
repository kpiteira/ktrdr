# Sandbox & Orchestrator: Architecture

## Overview

The autonomous coding system consists of two main components: a **Sandbox** (Docker container where Claude Code runs safely) and an **Orchestrator** (Python application on the host that manages the task loop). The orchestrator invokes Claude Code in the sandbox for both task implementation and E2E test execution, parsing JSON output to determine next steps.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Karl's Mac                                                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Orchestrator (Python)                                             │  │
│  │  ├─ State Manager (persistence, resume)                           │  │
│  │  ├─ Task Runner (invoke Claude, parse results)                    │  │
│  │  ├─ Escalation Handler (detect questions, wait for input)         │  │
│  │  ├─ E2E Runner (invoke Claude for tests)                          │  │
│  │  └─ Telemetry (OTel traces + metrics)───────────────────────────┐ │  │
│  └───────────────────────────────────────────────────────────────┐ │ │  │
│                                                                  │ │ │  │
│                                                                  ▼ ▼ ▼  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ KTRDR Observability Stack (existing)                              │  │
│  │  Jaeger (traces) │ Prometheus (metrics) │ Grafana (dashboards)    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                │                                                        │
│                │ docker exec                                            │
│                ▼                                                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Sandbox Container                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ Claude Code CLI                                              │  │  │
│  │  │  └─ Executes with: -p --output-format json --permission-mode │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                          │                                        │  │
│  │                          ▼                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ /workspace (git clone of ktrdr)                             │  │  │
│  │  │  ├─ .claude/ (copied from real repo)                        │  │  │
│  │  │  ├─ Full source code                                        │  │  │
│  │  │  └─ Can modify anything safely                              │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                          │                                        │  │
│  │                          │ docker socket                          │  │
│  │                          ▼                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ KTRDR Services (via docker compose)                         │  │  │
│  │  │  db, backend, workers, jaeger, prometheus, grafana           │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Real ktrdr repo (untouched by sandbox)                            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Orchestrator State                                                │  │
│  │  └─ state/{milestone}_state.json                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### Sandbox Container

**Responsibility**: Provide an isolated environment where Claude Code can execute with full permissions without affecting the real repository.

**Location**: `deploy/sandbox/Dockerfile`, `deploy/docker-compose.sandbox.yml`

**Dependencies**:

- Docker socket from host (for running ktrdr services)
- ANTHROPIC_API_KEY environment variable
- Reference mount to real repo's `.claude/` and `data/`

**Key Characteristics**:

- Ephemeral workspace: `/workspace` is a git clone, reset on demand
- Claude Code CLI installed via npm
- Docker CLI client (daemon runs on Mac)
- Python 3.11+ with uv for ktrdr development
- Network access to Docker network and internet

### Orchestrator

**Responsibility**: Manage the task execution loop, invoke Claude Code, handle escalations, and track progress.

**Location**: `orchestrator/` (Python package)

**Dependencies**:

- Docker (for `docker exec` to sandbox)
- Python 3.13+
- No external services required

#### Subcomponents

##### State Manager (`orchestrator/state.py`)

**Responsibility**: Persist orchestrator state for resumability.

**State Structure**:

```python
@dataclass
class OrchestratorState:
    milestone_id: str
    plan_path: str
    started_at: datetime
    current_task_index: int
    completed_tasks: list[str]
    failed_tasks: list[str]
    task_results: dict[str, TaskResult]
    e2e_status: str | None  # None, "pending", "passed", "failed"

    def save(self, path: Path) -> None:
        """Persist to JSON file."""

    @classmethod
    def load(cls, path: Path) -> "OrchestratorState":
        """Load from JSON file."""

    @classmethod
    def find_latest(cls, milestone_id: str) -> "OrchestratorState | None":
        """Find most recent state for milestone."""
```

**Storage**: `state/{milestone}_state.json`

##### Task Runner (`orchestrator/task_runner.py`)

**Responsibility**: Execute a single task via Claude Code in the sandbox.

**Interface**:

```python
@dataclass
class TaskResult:
    task_id: str
    status: Literal["completed", "failed", "needs_human"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    output: str
    question: str | None  # If needs_human
    options: list[str] | None
    recommendation: str | None
    error: str | None  # If failed
    session_id: str

async def run_task(
    task: Task,
    sandbox: SandboxManager,
    human_guidance: str | None = None,
) -> TaskResult:
    """Execute a task via Claude Code in the sandbox."""
```

**Claude Code Invocation**:

```bash
docker exec ktrdr-sandbox claude -p \
  --output-format json \
  --permission-mode acceptEdits \
  --max-turns 50 \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
  "/ktask impl: {plan_path} task: {task_id}

{human_guidance if provided}

When complete, include in your final message:
- STATUS: complete | needs_human | failed
- If needs_human: QUESTION: <question> OPTIONS: <options> RECOMMENDATION: <rec>
- If failed: ERROR: <what went wrong>"
```

##### Escalation Handler (`orchestrator/escalation.py`)

**Responsibility**: Detect when Claude needs human input, present the question, wait for response.

**Detection Heuristics**:

```python
def detect_needs_human(output: str) -> bool:
    """Detect if Claude is expressing uncertainty."""
    # Explicit markers (highest priority)
    if "NEEDS_HUMAN:" in output or "OPTIONS:" in output:
        return True

    # Question patterns
    question_patterns = [
        r"should I\s+",
        r"would you prefer",
        r"I'm not sure whether",
        r"the options (are|seem to be)",
        r"I recommend .+ but",
    ]
    for pattern in question_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return True

    return False

def extract_question(output: str) -> EscalationInfo:
    """Extract question, options, recommendation from output."""
```

**Escalation Flow**:

```python
async def escalate_and_wait(info: EscalationInfo) -> str:
    """Present question to user and wait for response."""
    # 1. Print formatted question to terminal
    print_escalation(info)

    # 2. Send macOS notification
    send_notification(
        title="Orchestrator needs input",
        message=f"Task {info.task_id}: {info.question[:50]}..."
    )

    # 3. Wait for user input
    response = input("Your response (or 'skip' for recommendation): ")

    if response.lower() == "skip" and info.recommendation:
        return info.recommendation
    return response
```

##### E2E Runner (`orchestrator/e2e_runner.py`)

**Responsibility**: Execute E2E tests via Claude Code, interpret results.

**Interface**:

```python
@dataclass
class E2EResult:
    status: Literal["passed", "failed", "unclear"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    diagnosis: str | None  # If failed
    fix_suggestion: str | None
    is_fixable: bool

async def run_e2e_tests(
    milestone: Milestone,
    sandbox: SandboxManager,
) -> E2EResult:
    """Execute milestone E2E tests via Claude Code."""
```

**Claude Code Invocation**:

```bash
docker exec ktrdr-sandbox claude -p \
  --output-format json \
  --permission-mode acceptEdits \
  --max-turns 30 \
  "Execute the following E2E test scenario for milestone {milestone_id}.
Run each command, observe results, and determine if the test passes.

{e2e_scenario_markdown}

After executing, report:
- E2E_STATUS: passed | failed
- If failed: DIAGNOSIS: <root cause analysis>
- If failed: FIXABLE: yes | no
- If fixable: FIX_SUGGESTION: <what to change>"
```

##### Telemetry (`orchestrator/telemetry.py`)

**Responsibility**: Emit OpenTelemetry traces and metrics to the existing KTRDR observability stack.

**Trace Structure**:

```
Trace: orchestrator.milestone (M4)
├── Span: orchestrator.sandbox_reset
│   └── Attributes: duration_seconds
├── Span: orchestrator.task (4.1)
│   ├── Span: orchestrator.claude_invoke
│   │   └── Attributes: tokens, cost_usd, turns, session_id
│   └── Attributes: status, duration_seconds
├── Span: orchestrator.task (4.2)
│   └── ...
├── Span: orchestrator.escalation
│   └── Attributes: question, response_time_seconds
├── Span: orchestrator.e2e_test
│   └── Attributes: status, diagnosis
└── Attributes: total_cost_usd, tasks_completed, tasks_failed
```

**Metrics**:

```python
# Counters
orchestrator_tasks_total{milestone, status}      # completed/failed/needs_human
orchestrator_tokens_total{milestone}
orchestrator_cost_usd_total{milestone}           # Cost tracking!
orchestrator_escalations_total{milestone}
orchestrator_e2e_tests_total{milestone, status}  # passed/failed

# Histograms
orchestrator_task_duration_seconds{milestone, task_id}
orchestrator_claude_invoke_duration_seconds{milestone}
orchestrator_sandbox_reset_duration_seconds
```

**Implementation**:

```python
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc import trace_exporter, metric_exporter

tracer = trace.get_tracer("orchestrator")
meter = metrics.get_meter("orchestrator")

# Counters
tasks_counter = meter.create_counter("orchestrator_tasks_total")
tokens_counter = meter.create_counter("orchestrator_tokens_total")
cost_counter = meter.create_counter("orchestrator_cost_usd_total")

# Histograms
task_duration = meter.create_histogram("orchestrator_task_duration_seconds")

@tracer.start_as_current_span("orchestrator.task")
async def run_task(task: Task, sandbox: SandboxManager) -> TaskResult:
    span = trace.get_current_span()
    span.set_attribute("task.id", task.id)
    span.set_attribute("milestone.id", task.milestone_id)

    result = await sandbox.invoke_claude(...)

    # Record attributes from Claude's JSON output
    span.set_attribute("claude.tokens", result.tokens_used)
    span.set_attribute("claude.cost_usd", result.cost_usd)
    span.set_attribute("claude.turns", result.num_turns)
    span.set_attribute("task.status", result.status)

    # Update metrics
    tasks_counter.add(1, {"milestone": task.milestone_id, "status": result.status})
    tokens_counter.add(result.tokens_used, {"milestone": task.milestone_id})
    cost_counter.add(result.cost_usd, {"milestone": task.milestone_id})
    task_duration.record(result.duration_seconds, {"milestone": task.milestone_id})

    return result
```

**OTLP Endpoint**: Uses same endpoint as ktrdr backend (`OTLP_ENDPOINT` env var, default `http://localhost:4317`)

##### Sandbox Manager (`orchestrator/sandbox.py`)

**Responsibility**: Manage sandbox container lifecycle.

**Interface**:

```python
class SandboxManager:
    async def ensure_running(self) -> None:
        """Ensure sandbox container is running."""

    async def reset(self) -> float:
        """Reset sandbox to clean state. Returns duration in seconds."""

    async def exec(self, command: str, timeout: int = 300) -> str:
        """Execute command in sandbox, return output."""

    async def invoke_claude(
        self,
        prompt: str,
        max_turns: int = 50,
        allowed_tools: list[str] | None = None,
    ) -> ClaudeResult:
        """Invoke Claude Code in sandbox with JSON output."""
```

---

## Data Flow

### Task Execution Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│ Orchestrator│────▶│ Task Runner  │────▶│ Sandbox     │────▶│ Claude   │
│ Main Loop   │     │              │     │ Manager     │     │ Code CLI │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────┘
       │                   │                    │                  │
       │  1. Get next task │                    │                  │
       │◀──────────────────│                    │                  │
       │                   │                    │                  │
       │  2. Run task      │                    │                  │
       │──────────────────▶│                    │                  │
       │                   │  3. docker exec    │                  │
       │                   │───────────────────▶│                  │
       │                   │                    │  4. claude -p    │
       │                   │                    │─────────────────▶│
       │                   │                    │                  │
       │                   │                    │  5. JSON result  │
       │                   │                    │◀─────────────────│
       │                   │  6. Parse result   │                  │
       │                   │◀──────────────────│                  │
       │  7. TaskResult    │                    │                  │
       │◀──────────────────│                    │                  │
       │                   │                    │                  │
       │  8. Log event     │                    │                  │
       │──────────────────▶│                    │                  │
       │  9. Update state  │                    │                  │
       │──────────────────▶│                    │                  │
```

### Escalation Flow

```
TaskResult.status == "needs_human"
       │
       ▼
┌──────────────────────────────────────┐
│ Escalation Handler                   │
│  1. Print question to terminal       │
│  2. Send macOS notification          │
│  3. Wait for input()                 │
└──────────────────────────────────────┘
       │
       ▼ (user types response)
       │
┌──────────────────────────────────────┐
│ Task Runner (retry)                  │
│  - Same task                         │
│  - human_guidance = user response    │
└──────────────────────────────────────┘
```

---

## API Contracts

### Claude Code JSON Output

**Input**: `claude -p "..." --output-format json`

**Output** (from Claude Code CLI):

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "total_cost_usd": 0.08,
  "duration_ms": 148000,
  "duration_api_ms": 142000,
  "num_turns": 6,
  "result": "... Claude's final message text ...",
  "session_id": "abc123-def456"
}
```

**Error case**:

```json
{
  "type": "result",
  "subtype": "error",
  "is_error": true,
  "result": "Error message...",
  "session_id": "abc123-def456"
}
```

### Orchestrator CLI

```bash
# Run a milestone
orchestrator run <milestone_id> [--notify] [--dry-run]

# Resume interrupted milestone
orchestrator resume <milestone_id>

# Reset sandbox
orchestrator sandbox reset

# Show run history
orchestrator history [--milestone <id>]

# Show cost summary
orchestrator costs [--since <date>]
```

---

## State Management

### Orchestrator State File

**Location**: `state/{milestone}_state.json`

**Structure**:

```json
{
  "milestone_id": "M4",
  "plan_path": "docs/milestones/M4_backtest.md",
  "started_at": "2024-01-15T14:23:01Z",
  "current_task_index": 2,
  "completed_tasks": ["4.1", "4.2"],
  "failed_tasks": [],
  "task_results": {
    "4.1": {
      "status": "completed",
      "duration_seconds": 148.0,
      "tokens_used": 12400,
      "cost_usd": 0.08,
      "session_id": "abc123"
    },
    "4.2": {
      "status": "completed",
      "duration_seconds": 42.0,
      "tokens_used": 3200,
      "cost_usd": 0.02,
      "session_id": "def456"
    }
  },
  "e2e_status": null
}
```

### Observability (OpenTelemetry)

**Traces**: Viewable in Jaeger at `http://localhost:16686`

- Search by service: `orchestrator`
- Search by tag: `milestone.id=M4`

**Metrics**: Queryable in Prometheus/Grafana at `http://localhost:3000`

- Cost tracking: `sum(orchestrator_cost_usd_total) by (milestone)`
- Task success rate: `sum(orchestrator_tasks_total{status="completed"}) / sum(orchestrator_tasks_total)`
- Average task duration: `histogram_quantile(0.5, orchestrator_task_duration_seconds)`

**Grafana Dashboard**: `deploy/shared/grafana/dashboards/orchestrator.json` (new)

- Milestone runs over time
- Cost per milestone
- Escalation frequency
- Task duration distribution

---

## Error Handling

### Task Failure

**When**: Claude Code returns `is_error: true` or output contains `STATUS: failed`

**Response**:

1. Log failure event
2. Attempt diagnosis via Claude Code
3. If fixable: attempt fix, re-run task
4. If not fixable: escalate to human

### Sandbox Crash

**When**: Docker container exits unexpectedly

**Response**:

1. Log error event
2. Restart container
3. Reset workspace
4. Resume from last completed task

### Claude Code Timeout

**When**: Task exceeds configured timeout (default: 10 minutes)

**Response**:

1. Kill the docker exec process
2. Log timeout event
3. Escalate to human with context

### Network Failure

**When**: Anthropic API unreachable

**Response**:

1. Retry with exponential backoff (3 attempts)
2. If persistent: escalate to human

---

## Integration Points

### Existing KTRDR Systems

| System | Integration | Notes |
|--------|-------------|-------|
| Implementation plans | Read markdown | Existing format works |
| E2E test scenarios | Read markdown | Existing format works |
| .claude/ commands | Copy to sandbox | /ktask, skills |
| Docker services | Via docker socket | Backend, workers, etc. |
| Data files | Read-only mount | For test execution |

| Jaeger | Trace viewing | Uses existing OTLP endpoint |
| Prometheus | Metrics collection | Uses existing OTLP endpoint |
| Grafana | Orchestrator dashboard | New dashboard in Phase 2 |

### Future Integration Points

| System | Integration | When |
|--------|-------------|------|
| GitHub Actions | Trigger orchestrator | Phase 6 |
| Slack/Discord | Escalation channel | Phase 6 |
| Other projects | Extract core | Phase 6 |

---

## File Structure

```
ktrdr/
├── deploy/
│   ├── sandbox/
│   │   ├── Dockerfile              # Sandbox container image
│   │   └── entrypoint.sh           # Container startup
│   └── docker-compose.sandbox.yml  # Sandbox compose config
│
├── scripts/
│   ├── sandbox-init.sh             # First-time sandbox setup
│   ├── sandbox-reset.sh            # Reset to clean state
│   ├── sandbox-shell.sh            # Interactive shell
│   └── sandbox-claude.sh           # Run Claude Code command
│
├── orchestrator/
│   ├── __init__.py
│   ├── __main__.py                 # CLI entry point
│   ├── cli.py                      # Click/Typer CLI
│   ├── config.py                   # Configuration
│   ├── models.py                   # Data classes
│   ├── plan_parser.py              # Parse milestone files
│   ├── task_runner.py              # Execute tasks
│   ├── e2e_runner.py               # Execute E2E tests
│   ├── escalation.py               # Human interaction
│   ├── sandbox.py                  # Sandbox management
│   ├── state.py                    # State persistence
│   └── telemetry.py                # OTel traces + metrics
│
├── state/                          # Orchestrator state files
│   └── {milestone}_state.json
│
└── deploy/shared/grafana/dashboards/
    └── orchestrator.json           # Grafana dashboard for orchestrator
```

---

## Security Considerations

### Sandbox Isolation

- Workspace is git clone, not bind mount of real repo
- Real repo is never modified by sandbox
- Container has no access to host filesystem except:
  - Docker socket (required for running services)
  - Read-only reference mounts for `.claude/` and `data/`

### API Key Handling

- ANTHROPIC_API_KEY passed as environment variable
- Not persisted in container or logs
- Same key Karl uses for manual Claude Code

### Docker Socket Access

- Required for Claude Code to run ktrdr services
- Sandbox can start/stop containers on the Docker network
- Mitigated by: ephemeral workspace, no host filesystem access

---

## Migration / Rollout

### Phase 1: Sandbox Only

1. Build and test sandbox container
2. Verify Claude Code works inside
3. Verify docker compose works inside
4. Create reset script
5. Manual testing with `/ktask`

### Phase 2: Basic Orchestrator

1. Build orchestrator CLI
2. Single task execution works
3. JSON parsing works
4. OTel telemetry works (traces + metrics)
5. Cost tracking from Claude output
6. Basic Grafana dashboard

### Phase 3-5: Full System

Incremental addition of:

- Task loop
- Escalation handling
- E2E integration
- Polish and robustness

No migration of existing data - this is a new system alongside existing workflow.

---

## References

- [DESIGN.md](DESIGN.md) - Design decisions and rationale
- [sandbox-orchestrator-handoff.md](sandbox-orchestrator-handoff.md) - Original design conversation
- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference.md) - Official docs
