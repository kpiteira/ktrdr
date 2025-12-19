---
design: docs/designs/orchestrator-health/DESIGN.md
architecture: docs/designs/orchestrator-health/ARCHITECTURE.md
---

# Milestone 1: Health Check Command

**Goal:** User can run `orchestrator health` and see system status with actionable error messages.

**Branch:** `feature/orchestrator-health`

---

## Task 1.1: Create health module with data classes

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Create the health module with `CheckResult` and `HealthReport` dataclasses, plus the dependency configuration.

**Implementation:**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

@dataclass
class CheckResult:
    status: Literal["ok", "failed", "skipped"]
    message: str
    check_name: str

@dataclass
class HealthReport:
    status: Literal["healthy", "unhealthy"]
    timestamp: datetime
    checks: dict[str, CheckResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "checks": {
                name: {"status": r.status, "message": r.message}
                for name, r in self.checks.items()
            }
        }

CHECK_DEPENDENCIES = {
    "sandbox": [],
    "claude_auth": ["sandbox"],
    "github_token": ["sandbox"],
    "orchestrator": [],
}

CHECK_ORDER = ["sandbox", "claude_auth", "github_token", "orchestrator"]
```

**Tests:** `orchestrator/tests/test_health.py`

- [ ] CheckResult can be instantiated with all three status values
- [ ] HealthReport.to_dict() produces expected JSON structure
- [ ] CHECK_ORDER contains all keys from CHECK_DEPENDENCIES

**Acceptance Criteria:**

- [ ] Module imports without error
- [ ] Dataclasses serialize correctly
- [ ] Unit tests pass

---

## Task 1.2: Implement individual check functions

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Implement the four check functions: `check_sandbox()`, `check_claude_auth()`, `check_github_token()`, `check_orchestrator()`.

**Implementation Notes:**

- Use `subprocess.run()` with `timeout=5` for docker commands
- `check_sandbox()`: `docker inspect --format '{{.State.Running}}' ktrdr-sandbox`
- `check_claude_auth()`: Check both `/home/ubuntu/.claude/credentials.json` and `/root/.claude/credentials.json`
- `check_github_token()`: `docker exec ktrdr-sandbox sh -c 'test -n "$GH_TOKEN"'`
- `check_orchestrator()`: Use `OrchestratorState.load()` from existing state module
- Container name from `OrchestratorConfig.sandbox_container`

**Tests:**

- [ ] check_sandbox() returns ok when container running (mock subprocess)
- [ ] check_sandbox() returns failed when container not running
- [ ] check_sandbox() returns failed on timeout
- [ ] check_claude_auth() returns ok when credentials.json exists
- [ ] check_claude_auth() returns failed when file missing
- [ ] check_github_token() returns ok when GH_TOKEN set
- [ ] check_github_token() returns failed when GH_TOKEN empty
- [ ] check_orchestrator() returns "idle" when no state file
- [ ] check_orchestrator() returns "working on task X.Y" when state exists

**Acceptance Criteria:**

- [ ] All four check functions implemented
- [ ] 5 second timeout on docker commands
- [ ] Actionable error messages on failure
- [ ] Unit tests pass with mocked subprocess

---

## Task 1.3: Implement get_health() aggregator

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Implement `get_health()` that runs checks in dependency order, skipping dependent checks when sandbox fails.

**Implementation:**

```python
def get_health(
    checks: list[str] | None = None,
    timeout: float = 5.0
) -> HealthReport:
    """Run health checks and return aggregated report."""
    checks_to_run = checks or CHECK_ORDER
    results: dict[str, CheckResult] = {}
    failed_checks: set[str] = set()

    for check_name in CHECK_ORDER:
        if check_name not in checks_to_run:
            continue

        # Check dependencies
        deps = CHECK_DEPENDENCIES.get(check_name, [])
        if any(dep in failed_checks for dep in deps):
            results[check_name] = CheckResult(
                status="skipped",
                message="sandbox not running",
                check_name=check_name
            )
            continue

        # Run the check
        result = _run_check(check_name, timeout)
        results[check_name] = result
        if result.status == "failed":
            failed_checks.add(check_name)

    overall = "unhealthy" if any(r.status == "failed" for r in results.values()) else "healthy"
    return HealthReport(status=overall, timestamp=datetime.utcnow(), checks=results)
```

**Tests:**

- [ ] All checks pass → status "healthy"
- [ ] Any check fails → status "unhealthy"
- [ ] Sandbox fails → claude_auth and github_token skipped
- [ ] Orchestrator always runs even if sandbox fails
- [ ] Single check mode (`checks=["sandbox"]`) runs only that check
- [ ] Skipped checks don't count as failures for overall status

**Acceptance Criteria:**

- [ ] Dependency ordering works correctly
- [ ] Skipped status used for dependent checks
- [ ] Overall status calculation correct
- [ ] Unit tests pass

---

## Task 1.4: Add health CLI command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator health` subcommand with `--check` option.

**Implementation Notes:**

- Add to existing Click CLI
- `--check` option accepts check name (sandbox, claude_auth, github_token, orchestrator)
- Output JSON to stdout
- Exit code 0 if healthy, 1 if unhealthy
- Follow pattern of existing commands in cli.py

```python
@cli.command()
@click.option("--check", type=click.Choice(CHECK_ORDER), help="Run single check")
def health(check: str | None):
    """Check orchestrator health status."""
    checks = [check] if check else None
    report = get_health(checks=checks)
    click.echo(json.dumps(report.to_dict(), indent=2))
    sys.exit(0 if report.status == "healthy" else 1)
```

**Tests:**

- [ ] `orchestrator health` runs all checks
- [ ] `orchestrator health --check sandbox` runs only sandbox
- [ ] Exit code 0 when healthy
- [ ] Exit code 1 when unhealthy
- [ ] Output is valid JSON

**Acceptance Criteria:**

- [ ] Command appears in `orchestrator --help`
- [ ] JSON output matches design spec
- [ ] Exit codes correct
- [ ] Unit tests pass

---

## Task 1.5: Add telemetry to health checks

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Wrap health checks with trace spans and metrics using existing telemetry module.

**Implementation Notes:**

- Use `orchestrator/telemetry.py` for tracing/metrics
- Parent span: `orchestrator.health`
- Child spans: `orchestrator.health.{check_name}`
- Counter: `orchestrator_health_checks_total` with `check` label
- Gauge: `orchestrator_health_check_status` (1=ok, 0=failed/skipped)

```python
from .telemetry import get_tracer, get_meter

tracer = get_tracer()
meter = get_meter()

health_checks_total = meter.create_counter(
    "orchestrator_health_checks_total",
    description="Total health checks performed"
)

health_check_status = meter.create_gauge(
    "orchestrator_health_check_status",
    description="Health check status (1=ok, 0=failed)"
)

def _run_check(check_name: str, timeout: float) -> CheckResult:
    with tracer.start_as_current_span(f"orchestrator.health.{check_name}") as span:
        result = CHECK_FUNCTIONS[check_name](timeout)
        span.set_attribute("check.status", result.status)
        span.set_attribute("check.message", result.message)
        health_checks_total.add(1, {"check": check_name})
        health_check_status.set(1 if result.status == "ok" else 0, {"check": check_name})
        return result
```

**Tests:**

- [ ] Trace span created for each check
- [ ] Span attributes set correctly
- [ ] Counter incremented on each check
- [ ] Gauge reflects current status

**Acceptance Criteria:**

- [ ] Traces visible in Jaeger when OTLP enabled
- [ ] Metrics exposed for Prometheus
- [ ] No errors when OTLP disabled
- [ ] Unit tests pass

---

## E2E Test Scenario

**Purpose:** Verify health command works end-to-end

**Prerequisites:** Sandbox container available (can be stopped for failure test)

```bash
# 1. Start sandbox if not running
./scripts/sandbox-init.sh

# 2. Test healthy state
orchestrator health
# Expected: exit 0, all checks ok

# 3. Verify JSON structure
orchestrator health | jq '.status'
# Expected: "healthy"

# 4. Test single check
orchestrator health --check sandbox | jq '.checks.sandbox.status'
# Expected: "ok"

# 5. Test failure (stop sandbox)
docker stop ktrdr-sandbox
orchestrator health
# Expected: exit 1, sandbox failed, claude_auth/github_token skipped

# 6. Verify skip behavior
orchestrator health | jq '.checks.claude_auth.status'
# Expected: "skipped"

# 7. Cleanup
docker start ktrdr-sandbox
```

**Success Criteria:**

- [ ] Exit code 0 when all checks pass
- [ ] Exit code 1 when any check fails
- [ ] Skipped status for dependent checks when sandbox down
- [ ] JSON output matches design spec
- [ ] No Python exceptions in any scenario

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/test_health.py -v`
- [ ] E2E test passes (above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions: `uv run pytest orchestrator/tests/ -v`
