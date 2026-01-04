---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Startability Gate + Status

**Goal:** Developer sees clear feedback when sandbox is ready, with health checks and service URLs.

**Branch:** `feature/sandbox-m3-gate`

**Builds on:** M2 (CLI Core)

---

## E2E Test Scenario

**Purpose:** Prove that `up` waits for health and reports clearly, and `status` shows all service URLs.

**Prerequisites:**
- M2 complete
- A sandbox instance exists

```bash
# 1. Create and start with gate
cd ../ktrdr--test-feature
ktrdr sandbox up

# Expected output (after ~30-60s):
# Starting instance: test-feature (slot 1)
#   ✓ Database ready
#   ✓ Backend healthy
#   ✓ Workers registered (4)
#   ✓ Observability ready
#
# Startability Gate: PASSED
#
# Instance ready:
#   API: http://localhost:8001/api/v1/docs
#   Grafana: http://localhost:3001
#   Jaeger: http://localhost:16687

# 2. Check detailed status
ktrdr sandbox status

# Expected output:
# Instance: test-feature (slot 1)
# Status: running
# Containers: 8/8 healthy
#
# Services:
#   Backend: http://localhost:8001 (healthy)
#   Database: localhost:5433 (ready)
#   Grafana: http://localhost:3001
#   Jaeger: http://localhost:16687
#   Prometheus: http://localhost:9091
#
# Workers:
#   backtest-worker-1: http://localhost:5010 (registered)
#   backtest-worker-2: http://localhost:5011 (registered)
#   training-worker-1: http://localhost:5012 (registered)
#   training-worker-2: http://localhost:5013 (registered)

# 3. Test gate failure detection (simulate by stopping backend)
docker stop ktrdr--test-feature-backend-1
ktrdr sandbox up  # Should detect and report failure

# Expected output:
# Startability Gate: FAILED
#
# ✓ Database ready
# ✗ Backend health check failed
#   → GET http://localhost:8001/api/v1/health returned connection refused
# ✗ Workers not registered
#   → Expected 4 workers, found 0
```

**Success Criteria:**
- [ ] `up` performs health checks before reporting ready
- [ ] Gate shows individual check results (✓/✗)
- [ ] `status` shows all service URLs
- [ ] Failed checks include helpful diagnostics

---

## Tasks

### Task 3.1: Create Startability Gate Module

**File:** `ktrdr/cli/sandbox_gate.py` (new)
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component, External

**Description:**
Implement the Startability Gate that validates a sandbox instance is fully ready.

**Implementation Notes:**

```python
"""Startability Gate for sandbox instances."""

import asyncio
from dataclasses import dataclass
from enum import Enum
import httpx


class CheckStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    status: CheckStatus
    message: str = ""
    details: str = ""


@dataclass
class GateResult:
    """Overall Startability Gate result."""
    passed: bool
    checks: list[CheckResult]
    duration_seconds: float


class StartabilityGate:
    """Validates that a sandbox instance is ready for use."""

    def __init__(self, api_port: int, db_port: int, timeout: float = 120.0):
        self.api_port = api_port
        self.db_port = db_port
        self.timeout = timeout
        self.poll_interval = 2.0

    async def check(self) -> GateResult:
        """Run all health checks."""
        import time
        start = time.time()

        checks = []
        deadline = start + self.timeout

        # Check database first (backend depends on it)
        db_result = await self._poll_until(
            self._check_database, "Database", deadline
        )
        checks.append(db_result)

        # Check backend health
        backend_result = await self._poll_until(
            self._check_backend_health, "Backend", deadline
        )
        checks.append(backend_result)

        # Check workers registered (only if backend is up)
        if backend_result.status == CheckStatus.PASSED:
            workers_result = await self._poll_until(
                self._check_workers_registered, "Workers", deadline
            )
            checks.append(workers_result)
        else:
            checks.append(CheckResult(
                name="Workers",
                status=CheckStatus.SKIPPED,
                message="Skipped (backend not ready)"
            ))

        # Check observability
        obs_result = await self._poll_until(
            self._check_observability, "Observability", deadline
        )
        checks.append(obs_result)

        duration = time.time() - start
        passed = all(c.status == CheckStatus.PASSED for c in checks
                     if c.status != CheckStatus.SKIPPED)

        return GateResult(passed=passed, checks=checks, duration_seconds=duration)

    async def _poll_until(
        self,
        check_fn,
        name: str,
        deadline: float
    ) -> CheckResult:
        """Poll a check until it passes or deadline reached."""
        import time
        last_error = ""

        while time.time() < deadline:
            try:
                result = await check_fn()
                if result.status == CheckStatus.PASSED:
                    return result
                last_error = result.message
            except Exception as e:
                last_error = str(e)

            await asyncio.sleep(self.poll_interval)

        return CheckResult(
            name=name,
            status=CheckStatus.FAILED,
            message=f"Timeout after {self.timeout}s",
            details=last_error
        )

    async def _check_database(self) -> CheckResult:
        """Check if database is ready using pg_isready pattern."""
        import socket
        try:
            with socket.create_connection(("localhost", self.db_port), timeout=5):
                return CheckResult(
                    name="Database",
                    status=CheckStatus.PASSED,
                    message="Connection accepted"
                )
        except (socket.timeout, ConnectionRefusedError) as e:
            return CheckResult(
                name="Database",
                status=CheckStatus.FAILED,
                message=str(e)
            )

    async def _check_backend_health(self) -> CheckResult:
        """Check backend /health endpoint."""
        url = f"http://localhost:{self.api_port}/api/v1/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return CheckResult(
                        name="Backend",
                        status=CheckStatus.PASSED,
                        message=f"GET {url} → 200"
                    )
                return CheckResult(
                    name="Backend",
                    status=CheckStatus.FAILED,
                    message=f"GET {url} → {resp.status_code}"
                )
        except httpx.ConnectError:
            return CheckResult(
                name="Backend",
                status=CheckStatus.FAILED,
                message="Connection refused"
            )

    async def _check_workers_registered(self) -> CheckResult:
        """Check that expected workers are registered."""
        url = f"http://localhost:{self.api_port}/api/v1/workers"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return CheckResult(
                        name="Workers",
                        status=CheckStatus.FAILED,
                        message=f"GET {url} → {resp.status_code}"
                    )

                data = resp.json()
                workers = data.get("workers", [])
                count = len(workers)

                if count >= 4:
                    return CheckResult(
                        name="Workers",
                        status=CheckStatus.PASSED,
                        message=f"{count} workers registered"
                    )
                return CheckResult(
                    name="Workers",
                    status=CheckStatus.FAILED,
                    message=f"Expected 4 workers, found {count}"
                )
        except Exception as e:
            return CheckResult(
                name="Workers",
                status=CheckStatus.FAILED,
                message=str(e)
            )

    async def _check_observability(self) -> CheckResult:
        """Check Jaeger UI is responding."""
        url = f"http://localhost:{16686 + (self.api_port - 8000)}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code in (200, 302):
                    return CheckResult(
                        name="Observability",
                        status=CheckStatus.PASSED,
                        message="Jaeger UI responding"
                    )
                return CheckResult(
                    name="Observability",
                    status=CheckStatus.FAILED,
                    message=f"Jaeger returned {resp.status_code}"
                )
        except httpx.ConnectError:
            return CheckResult(
                name="Observability",
                status=CheckStatus.FAILED,
                message="Jaeger not responding"
            )


def run_gate(api_port: int, db_port: int, timeout: float = 120.0) -> GateResult:
    """Synchronous wrapper for running the gate."""
    gate = StartabilityGate(api_port, db_port, timeout)
    return asyncio.run(gate.check())
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_gate.py`
- [ ] `test_check_result_dataclass` — Verify CheckResult fields
- [ ] `test_gate_result_passed_when_all_pass` — All checks pass → passed=True
- [ ] `test_gate_result_failed_when_any_fail` — One fails → passed=False
- [ ] `test_skipped_checks_dont_fail_gate` — Skipped checks don't affect result

*Integration Tests:*
- [ ] `test_gate_passes_on_healthy_stack` — With running stack, gate passes
- [ ] `test_gate_fails_on_stopped_backend` — With stopped backend, gate fails
- [ ] `test_gate_timeout_respected` — Gate respects timeout setting

*Smoke Test:*
```python
from ktrdr.cli.sandbox_gate import run_gate
result = run_gate(api_port=8001, db_port=5433, timeout=60)
print(f"Passed: {result.passed}")
for check in result.checks:
    print(f"  {check.name}: {check.status.value} - {check.message}")
```

**Acceptance Criteria:**
- [ ] All four checks implemented (db, backend, workers, observability)
- [ ] Polling with timeout works
- [ ] Results include helpful messages
- [ ] Async implementation for parallel checking

---

### Task 3.2: Integrate Gate into `sandbox up`

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Wiring/DI

**Description:**
Modify the `up` command to run the Startability Gate and display results.

**Implementation Notes:**

```python
from ktrdr.cli.sandbox_gate import run_gate, CheckStatus


@sandbox_app.command()
def up(
    no_wait: bool = typer.Option(False, "--no-wait", help="Don't wait for Startability Gate"),
    build: bool = typer.Option(False, "--build", help="Force rebuild images"),
    timeout: int = typer.Option(120, "--timeout", help="Gate timeout in seconds"),
):
    """Start the sandbox stack."""
    # ... existing code to start compose ...

    if no_wait:
        console.print("\nInstance starting... (use 'ktrdr sandbox status' to check)")
        return

    # Run Startability Gate
    console.print("\nRunning Startability Gate...")
    api_port = int(env.get("KTRDR_API_PORT", 8000))
    db_port = int(env.get("KTRDR_DB_PORT", 5432))

    result = run_gate(api_port, db_port, timeout=float(timeout))

    # Display results
    for check in result.checks:
        if check.status == CheckStatus.PASSED:
            console.print(f"  [green]✓[/green] {check.name} ready")
        elif check.status == CheckStatus.SKIPPED:
            console.print(f"  [dim]○[/dim] {check.name} skipped")
        else:
            console.print(f"  [red]✗[/red] {check.name} failed")
            if check.message:
                console.print(f"    → {check.message}")
            if check.details:
                console.print(f"    → {check.details}")

    console.print()

    if result.passed:
        console.print("[green]Startability Gate: PASSED[/green]")
        console.print(f"\nInstance ready ({result.duration_seconds:.1f}s):")
        console.print(f"  API: http://localhost:{api_port}/api/v1/docs")
        console.print(f"  Grafana: http://localhost:{env.get('KTRDR_GRAFANA_PORT', 3000)}")
        console.print(f"  Jaeger: http://localhost:{env.get('KTRDR_JAEGER_UI_PORT', 16686)}")
    else:
        error_console.print("[red]Startability Gate: FAILED[/red]")
        error_console.print("\nCheck logs with: ktrdr sandbox logs")
        raise typer.Exit(2)
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_up_runs_gate_by_default` — Without --no-wait, gate runs
- [ ] `test_up_no_wait_skips_gate` — With --no-wait, no gate
- [ ] `test_up_exits_on_gate_failure` — Exit code 2 on failure

*Smoke Test:*
```bash
ktrdr sandbox up
# Should see gate results
```

**Acceptance Criteria:**
- [ ] Gate runs by default on `up`
- [ ] `--no-wait` skips gate
- [ ] Clear display of check results
- [ ] Exit code 2 on gate failure

---

### Task 3.3: Implement `ktrdr sandbox status` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint (CLI), Cross-Component

**Description:**
Implement `status` command that shows detailed instance status with all service URLs.

**Implementation Notes:**

```python
@sandbox_app.command()
def status():
    """Show detailed status of current sandbox instance."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")
    slot = env.get("SLOT_NUMBER", "?")

    console.print(f"[bold]Instance:[/bold] {instance_id} (slot {slot})")

    # Get container status
    try:
        compose_file = find_compose_file(cwd)
        import os
        compose_env = os.environ.copy()
        compose_env.update(env)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
            capture_output=True, text=True, env=compose_env
        )

        import json
        containers = json.loads(result.stdout) if result.stdout else []

        running = sum(1 for c in containers if c.get("State") == "running")
        total = len(containers)

        if running == total and total > 0:
            status_str = "[green]running[/green]"
        elif running > 0:
            status_str = f"[yellow]partial ({running}/{total})[/yellow]"
        elif total > 0:
            status_str = "[red]stopped[/red]"
        else:
            status_str = "[dim]not started[/dim]"

        console.print(f"[bold]Status:[/bold] {status_str}")
        console.print(f"[bold]Containers:[/bold] {running}/{total} healthy")

    except Exception as e:
        console.print(f"[bold]Status:[/bold] [red]error ({e})[/red]")

    console.print()

    # Service URLs
    api_port = env.get("KTRDR_API_PORT", "8000")
    db_port = env.get("KTRDR_DB_PORT", "5432")
    grafana_port = env.get("KTRDR_GRAFANA_PORT", "3000")
    jaeger_port = env.get("KTRDR_JAEGER_UI_PORT", "16686")
    prometheus_port = env.get("KTRDR_PROMETHEUS_PORT", "9090")

    console.print("[bold]Services:[/bold]")
    console.print(f"  Backend:    http://localhost:{api_port}")
    console.print(f"  API Docs:   http://localhost:{api_port}/api/v1/docs")
    console.print(f"  Database:   localhost:{db_port}")
    console.print(f"  Grafana:    http://localhost:{grafana_port}")
    console.print(f"  Jaeger:     http://localhost:{jaeger_port}")
    console.print(f"  Prometheus: http://localhost:{prometheus_port}")

    console.print()
    console.print("[bold]Workers:[/bold]")
    for i in range(1, 5):
        port = env.get(f"KTRDR_WORKER_PORT_{i}", "?")
        console.print(f"  Worker {i}:   http://localhost:{port}")
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_status_shows_instance_info` — Shows instance ID and slot
- [ ] `test_status_shows_container_counts` — Shows running/total
- [ ] `test_status_shows_urls` — All service URLs displayed

*Smoke Test:*
```bash
ktrdr sandbox status
```

**Acceptance Criteria:**
- [ ] Shows instance ID, slot, status
- [ ] Shows container health counts
- [ ] Lists all service URLs
- [ ] Works in running and stopped states

---

### Task 3.4: Add Port Conflict Detection to `up`

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Check for port conflicts before starting `docker compose up`.

**Implementation Notes:**

```python
# Add to up() command, before docker compose up:

from ktrdr.cli.sandbox_ports import check_ports_available

slot = int(env.get("SLOT_NUMBER", 0))
conflicts = check_ports_available(slot)
if conflicts:
    error_console.print(f"[red]Error:[/red] Ports already in use: {conflicts}")
    error_console.print("\nThis could be:")
    error_console.print("  - Another sandbox running on the same slot")
    error_console.print("  - External process using these ports")
    error_console.print("\nUse 'lsof -i :<port>' to identify the process.")
    raise typer.Exit(3)
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_up_detects_port_conflict` — Bind a port, `up` fails with exit 3
- [ ] `test_up_proceeds_when_ports_free` — No conflicts, proceeds normally

*Smoke Test:*
```bash
# Bind a port to simulate conflict
python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 8001)); input()" &
ktrdr sandbox up  # Should fail with port conflict
kill %1
```

**Acceptance Criteria:**
- [ ] Detects port conflicts before starting compose
- [ ] Clear error message with conflicting ports
- [ ] Suggests diagnostic commands

---

### Task 3.5: Implement `ktrdr sandbox logs` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** API Endpoint (CLI)

**Description:**
Implement `logs` command to view service logs.

**Implementation Notes:**

```python
@sandbox_app.command()
def logs(
    service: str = typer.Argument(None, help="Service name (e.g., backend, db)"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
):
    """View logs for sandbox services."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    try:
        compose_file = find_compose_file(cwd)
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        raise typer.Exit(1)

    import os
    compose_env = os.environ.copy()
    compose_env.update(env)

    cmd = ["docker", "compose", "-f", str(compose_file), "logs"]
    cmd.extend(["--tail", str(tail)])
    if follow:
        cmd.append("-f")
    if service:
        cmd.append(service)

    try:
        subprocess.run(cmd, env=compose_env)
    except KeyboardInterrupt:
        pass  # Normal exit from follow mode
```

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr sandbox logs backend --tail 20
ktrdr sandbox logs -f  # Ctrl+C to exit
```

**Acceptance Criteria:**
- [ ] Shows logs for all services by default
- [ ] `--follow` streams logs
- [ ] `--tail` controls line count
- [ ] Service name filters to single service

---

## Completion Checklist

- [ ] All 5 tasks complete and committed
- [ ] `sandbox_gate.py` created with all checks
- [ ] Gate integrated into `up` command
- [ ] `status` command shows all URLs
- [ ] Port conflict detection works
- [ ] `logs` command works
- [ ] E2E test passes
- [ ] Unit tests pass
- [ ] Quality gates pass: `make quality`

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| Startability Gate | `sandbox_gate.py` with 4 health checks |
| Polling with timeout | `_poll_until()` with configurable timeout |
| Clear feedback | Rich console output with ✓/✗ symbols |
