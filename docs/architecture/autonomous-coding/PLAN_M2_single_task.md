# Milestone 2: Single Task Execution + Telemetry

**Branch:** `feature/orchestrator-m2-single-task`
**Builds on:** M1 (sandbox works)
**Estimated Tasks:** 9

---

## Capability

Orchestrator executes a single task via Claude Code in the sandbox, captures structured result (status, tokens, cost), and emits OpenTelemetry traces to Jaeger.

---

## E2E Test Scenario

```bash
# 1. Ensure sandbox is running
docker compose -f deploy/environments/sandbox/docker-compose.yml up -d

# 2. Run a simple task
uv run orchestrator task orchestrator/test_plans/hello_world.md 1.1

# Expected output:
# [timestamp] Task 1.1: Create hello.py
#             Invoking Claude Code...
# [timestamp] Task 1.1: COMPLETED (45s, 3.2k tokens, $0.02)

# 3. Verify task was executed
docker exec ktrdr-sandbox cat /workspace/hello.py
docker exec ktrdr-sandbox python /workspace/hello.py
# Expect: "Hello, World!"

# 4. Verify trace in Jaeger
curl -s "http://localhost:16686/api/traces?service=orchestrator&limit=1" | \
  jq '.data[0].spans[] | {operation: .operationName, tags: [.tags[] | select(.key | startswith("claude") or startswith("task"))]}'
# Expect: orchestrator.task span with claude.tokens, claude.cost_usd, task.status

# 5. Verify metrics in Prometheus
curl -s "http://localhost:9090/api/v1/query?query=orchestrator_tasks_total" | jq '.data.result'
# Expect: counter with status="completed"
```

---

## Tasks

### Task 2.1: Create Orchestrator Package Structure

**Files:**
- `orchestrator/__init__.py`
- `orchestrator/__main__.py`
- `orchestrator/py.typed`
- `pyproject.toml` (add orchestrator entry point)

**Type:** CODING

**Description:**
Set up the orchestrator as a Python package with entry point.

**Implementation Notes:**
- Add to existing pyproject.toml or create separate one in orchestrator/
- Entry point: `orchestrator = "orchestrator.__main__:main"`
- Use Python 3.11+ features (typing, dataclasses)

**Acceptance Criteria:**
- [ ] `uv run orchestrator --help` works
- [ ] Package is importable
- [ ] Type hints enabled (py.typed marker)

---

### Task 2.2: Create Configuration Module

**File:** `orchestrator/config.py`
**Type:** CODING

**Description:**
Configuration dataclass with defaults and environment variable overrides.

**Implementation Notes:**
```python
from dataclasses import dataclass, field
from pathlib import Path
import os

@dataclass
class OrchestratorConfig:
    # Sandbox
    sandbox_container: str = "ktrdr-sandbox"
    workspace_path: str = "/workspace"

    # Claude Code
    max_turns: int = 50
    task_timeout_seconds: int = 600
    allowed_tools: list[str] = field(default_factory=lambda: [
        "Bash", "Read", "Write", "Edit", "Glob", "Grep"
    ])

    # Telemetry
    otlp_endpoint: str = field(
        default_factory=lambda: os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
    )
    service_name: str = "orchestrator"

    # State
    state_dir: Path = field(default_factory=lambda: Path("state"))

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        """Load config with environment variable overrides."""
        return cls(
            max_turns=int(os.getenv("ORCHESTRATOR_MAX_TURNS", "50")),
            task_timeout_seconds=int(os.getenv("ORCHESTRATOR_TASK_TIMEOUT", "600")),
            otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
        )
```

**Acceptance Criteria:**
- [ ] Config loads with sensible defaults
- [ ] Environment variables override defaults
- [ ] All fields have type hints

---

### Task 2.3: Create Data Models

**File:** `orchestrator/models.py`
**Type:** CODING

**Description:**
Data classes for tasks, results, and Claude output.

**Implementation Notes:**
```python
from dataclasses import dataclass
from typing import Literal
from datetime import datetime

@dataclass
class Task:
    id: str
    title: str
    description: str
    file_path: str | None
    acceptance_criteria: list[str]
    plan_file: str
    milestone_id: str

@dataclass
class ClaudeResult:
    is_error: bool
    result: str
    total_cost_usd: float
    duration_ms: int
    num_turns: int
    session_id: str

@dataclass
class TaskResult:
    task_id: str
    status: Literal["completed", "failed", "needs_human"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    output: str
    session_id: str
    # If needs_human
    question: str | None = None
    options: list[str] | None = None
    recommendation: str | None = None
    # If failed
    error: str | None = None
```

**Acceptance Criteria:**
- [ ] All models have type hints
- [ ] Models are JSON serializable (for state persistence)
- [ ] TaskResult covers all three status types

---

### Task 2.4: Create Plan Parser

**File:** `orchestrator/plan_parser.py`
**Type:** CODING

**Description:**
Parse milestone markdown files to extract tasks.

**Implementation Notes:**
- Parse markdown headers to find tasks (## Task X.Y: Title)
- Extract description, file paths, acceptance criteria
- Handle various formats (be lenient)
- Return list of Task objects

**Example Input:**
```markdown
# Milestone 1: Something

## Task 1.1: Create hello.py

**File:** hello.py
**Description:** Create a file that prints hello

**Acceptance Criteria:**
- [ ] File exists
- [ ] Prints "Hello, World!"
```

**Acceptance Criteria:**
- [ ] Parses task ID from header
- [ ] Extracts file path if present
- [ ] Extracts acceptance criteria
- [ ] Handles missing optional fields gracefully
- [ ] Unit tests cover edge cases

---

### Task 2.5: Create Sandbox Manager

**File:** `orchestrator/sandbox.py`
**Type:** CODING

**Description:**
Manage sandbox container interaction via docker exec.

**Implementation Notes:**
```python
import subprocess
import json
from dataclasses import dataclass

@dataclass
class SandboxManager:
    container_name: str = "ktrdr-sandbox"
    workspace_path: str = "/workspace"

    async def exec(self, command: str, timeout: int = 300) -> str:
        """Execute command in sandbox, return output."""
        result = subprocess.run(
            ["docker", "exec", self.container_name, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise SandboxError(f"Command failed: {result.stderr}")
        return result.stdout

    async def invoke_claude(
        self,
        prompt: str,
        max_turns: int = 50,
        allowed_tools: list[str] | None = None,
        timeout: int = 600,
    ) -> ClaudeResult:
        """Invoke Claude Code in sandbox with JSON output."""
        tools = allowed_tools or ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]

        cmd = [
            "docker", "exec", "-w", self.workspace_path, self.container_name,
            "claude", "-p", prompt,
            "--output-format", "json",
            "--permission-mode", "acceptEdits",
            "--max-turns", str(max_turns),
            "--allowedTools", ",".join(tools),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        # Parse JSON output
        output = json.loads(result.stdout)
        return ClaudeResult(
            is_error=output.get("is_error", False),
            result=output.get("result", ""),
            total_cost_usd=output.get("total_cost_usd", 0.0),
            duration_ms=output.get("duration_ms", 0),
            num_turns=output.get("num_turns", 0),
            session_id=output.get("session_id", ""),
        )
```

**Acceptance Criteria:**
- [ ] exec() runs commands and returns output
- [ ] invoke_claude() returns parsed ClaudeResult
- [ ] Timeout handling works
- [ ] Error cases raise appropriate exceptions

---

### Task 2.6: Create Task Runner

**File:** `orchestrator/task_runner.py`
**Type:** CODING

**Description:**
Execute a single task via Claude Code and parse the result.

**Implementation Notes:**
```python
async def run_task(
    task: Task,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    human_guidance: str | None = None,
) -> TaskResult:
    """Execute a task via Claude Code in the sandbox."""

    prompt = f"""
/ktask impl: {task.plan_file} task: {task.id}

{f"Additional guidance: {human_guidance}" if human_guidance else ""}

When complete, include in your final message:
- STATUS: complete | needs_human | failed
- If needs_human: QUESTION: <question> OPTIONS: <options> RECOMMENDATION: <rec>
- If failed: ERROR: <what went wrong>
"""

    start_time = time.time()
    claude_result = await sandbox.invoke_claude(
        prompt=prompt,
        max_turns=config.max_turns,
        timeout=config.task_timeout_seconds,
    )
    duration = time.time() - start_time

    # Parse status from Claude's output
    status, question, options, recommendation, error = parse_task_output(claude_result.result)

    return TaskResult(
        task_id=task.id,
        status=status,
        duration_seconds=duration,
        tokens_used=estimate_tokens(claude_result),  # From cost
        cost_usd=claude_result.total_cost_usd,
        output=claude_result.result,
        session_id=claude_result.session_id,
        question=question,
        options=options,
        recommendation=recommendation,
        error=error,
    )
```

**Acceptance Criteria:**
- [ ] Constructs proper prompt with /ktask
- [ ] Parses STATUS from Claude output
- [ ] Extracts question/options/recommendation for needs_human
- [ ] Extracts error for failed
- [ ] Returns complete TaskResult

---

### Task 2.7: Create Telemetry Module

**File:** `orchestrator/telemetry.py`
**Type:** CODING

**Description:**
Set up OpenTelemetry tracing and metrics.

**Implementation Notes:**
```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def setup_telemetry(config: OrchestratorConfig) -> tuple[trace.Tracer, metrics.Meter]:
    """Initialize OpenTelemetry with OTLP export."""

    # Tracing
    trace_provider = TracerProvider()
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otlp_endpoint))
    )
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(config.service_name)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=config.otlp_endpoint)
    )
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(config.service_name)

    return tracer, meter

# Metrics
tasks_counter: metrics.Counter
tokens_counter: metrics.Counter
cost_counter: metrics.Counter

def create_metrics(meter: metrics.Meter):
    global tasks_counter, tokens_counter, cost_counter

    tasks_counter = meter.create_counter(
        "orchestrator_tasks_total",
        description="Total tasks executed",
    )
    tokens_counter = meter.create_counter(
        "orchestrator_tokens_total",
        description="Total tokens used",
    )
    cost_counter = meter.create_counter(
        "orchestrator_cost_usd_total",
        description="Total cost in USD",
    )
```

**Acceptance Criteria:**
- [ ] Traces export to Jaeger via OTLP
- [ ] Metrics export to Prometheus via OTLP
- [ ] Tracer and meter are accessible throughout app
- [ ] Service name is "orchestrator"

---

### Task 2.8: Create CLI with Task Command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
CLI entry point with `task` command for single task execution.

**Implementation Notes:**
```python
import asyncio
import click
from rich.console import Console

console = Console()

@click.group()
def cli():
    """Orchestrator - Autonomous task execution for KTRDR."""
    pass

@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.argument("task_id")
@click.option("--guidance", "-g", help="Additional guidance for Claude")
def task(plan_file: str, task_id: str, guidance: str | None):
    """Execute a single task from a plan file."""
    asyncio.run(_run_task(plan_file, task_id, guidance))

async def _run_task(plan_file: str, task_id: str, guidance: str | None):
    config = OrchestratorConfig.from_env()
    tracer, meter = setup_telemetry(config)
    create_metrics(meter)

    # Parse plan
    tasks = parse_plan(plan_file)
    task = next((t for t in tasks if t.id == task_id), None)
    if not task:
        console.print(f"[red]Task {task_id} not found in {plan_file}[/red]")
        return

    sandbox = SandboxManager()

    with tracer.start_as_current_span("orchestrator.task") as span:
        span.set_attribute("task.id", task_id)
        span.set_attribute("task.title", task.title)

        console.print(f"[bold]Task {task_id}:[/bold] {task.title}")
        console.print("Invoking Claude Code...")

        result = await run_task(task, sandbox, config, guidance)

        # Record telemetry
        span.set_attribute("task.status", result.status)
        span.set_attribute("claude.tokens", result.tokens_used)
        span.set_attribute("claude.cost_usd", result.cost_usd)
        span.set_attribute("claude.session_id", result.session_id)

        tasks_counter.add(1, {"status": result.status})
        tokens_counter.add(result.tokens_used)
        cost_counter.add(result.cost_usd)

        # Output
        status_color = {"completed": "green", "failed": "red", "needs_human": "yellow"}
        console.print(
            f"Task {task_id}: [bold {status_color[result.status]}]{result.status.upper()}[/bold] "
            f"({result.duration_seconds:.0f}s, {result.tokens_used/1000:.1f}k tokens, ${result.cost_usd:.2f})"
        )

if __name__ == "__main__":
    cli()
```

**Acceptance Criteria:**
- [ ] `orchestrator task <plan> <task_id>` works
- [ ] Outputs status, duration, tokens, cost
- [ ] Emits trace with attributes
- [ ] Updates metrics counters

---

### Task 2.9: Create Test Plans

**Files:**
- `orchestrator/test_plans/hello_world.md`
- `orchestrator/test_plans/health_check.md`

**Type:** CODING

**Description:**
Create test plan files for validation.

**hello_world.md:**
```markdown
# Test Milestone: Hello World

## Task 1.1: Create hello.py

**File:** `hello.py`
**Type:** CODING

**Description:**
Create a Python file that prints "Hello, World!" when executed.

**Acceptance Criteria:**
- [ ] File `hello.py` exists in workspace root
- [ ] Running `python hello.py` outputs "Hello, World!"
```

**health_check.md:** (for M3 validation)
```markdown
# Milestone: Orchestrator Health Check

A simple 3-task milestone for validating the orchestrator.

## Task 1.1: Create health module

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Create a health module that returns system status.

**Implementation Notes:**
- Function `get_health() -> dict` returns {"status": "ok", "timestamp": ...}
- Check if sandbox container is running
- Return status info

**Acceptance Criteria:**
- [ ] File exists
- [ ] Function returns dict with "status" key
- [ ] Importable without errors

---

## Task 1.2: Add health CLI command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator health` command that calls the health module.

**Acceptance Criteria:**
- [ ] `orchestrator health` command exists
- [ ] Outputs JSON health status
- [ ] Returns exit code 0 on healthy

---

## Task 1.3: Add health telemetry

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Emit a metric when health is checked.

**Acceptance Criteria:**
- [ ] `orchestrator_health_checks_total` counter increments
- [ ] Trace span created for health check

---

## E2E Test

```bash
# Run health check
orchestrator health

# Expected output (JSON):
# {"status": "ok", "timestamp": "2024-...", "sandbox": "running"}

# Verify in Jaeger:
# orchestrator.health_check span exists
```
```

**Acceptance Criteria:**
- [ ] hello_world.md is parseable by plan_parser
- [ ] health_check.md has 3 tasks with clear criteria
- [ ] E2E test section is present

---

## Milestone Verification

**Validation with hello_world.md:**
```bash
# Reset sandbox
./scripts/sandbox-reset.sh

# Run task
uv run orchestrator task orchestrator/test_plans/hello_world.md 1.1

# Verify
docker exec ktrdr-sandbox python /workspace/hello.py
# Expect: Hello, World!

# Check Jaeger
open http://localhost:16686
# Search service=orchestrator, expect task span with attributes
```

**Validation with health_check.md Task 1 only:**
```bash
# Run just task 1.1 from health_check
uv run orchestrator task orchestrator/test_plans/health_check.md 1.1

# Verify file created
docker exec ktrdr-sandbox cat /workspace/orchestrator/health.py
```

**Checklist:**
- [ ] All tasks complete
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/`
- [ ] E2E test passes: hello_world.md task executes
- [ ] Telemetry works: traces visible in Jaeger
- [ ] Quality gates pass: `make quality`
