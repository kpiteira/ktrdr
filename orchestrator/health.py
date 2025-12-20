"""Health check module for the Orchestrator.

Provides health check data models and dependency configuration for verifying
system readiness before task execution. Includes CheckResult for individual
checks and HealthReport for aggregated status.

Telemetry is optional: traces and metrics are recorded when OTLP is enabled,
but health checks work correctly without it.
"""

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from opentelemetry import metrics, trace

# Default timeout for health check commands (seconds)
HEALTH_CHECK_TIMEOUT = 5

# Default container name (can be overridden)
DEFAULT_CONTAINER = "ktrdr-sandbox"


@dataclass
class CheckResult:
    """Result of a single health check.

    Represents the outcome of checking one system component (sandbox, claude_auth,
    github_token, or orchestrator).

    Attributes:
        status: Check outcome - "ok" if passed, "failed" if error, "skipped" if
            a dependency failed
        message: Human-readable description of the result, including actionable
            guidance for failures
        check_name: Name of the check (e.g., "sandbox", "claude_auth")
    """

    status: Literal["ok", "failed", "skipped"]
    message: str
    check_name: str


@dataclass
class HealthReport:
    """Aggregated health report from all checks.

    Contains overall system status and individual check results.

    Attributes:
        status: Overall health - "healthy" if all checks pass, "unhealthy" if
            any check fails
        timestamp: When the health check was performed
        checks: Map of check name to CheckResult
    """

    status: Literal["healthy", "unhealthy"]
    timestamp: datetime
    checks: dict[str, CheckResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict.

        Returns:
            Dict with status, ISO-formatted timestamp, and checks as nested dicts.
        """
        return {
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "checks": {
                name: {"status": result.status, "message": result.message}
                for name, result in self.checks.items()
            },
        }


# Dependency graph for health checks.
# If a check's dependency fails, the check is skipped.
CHECK_DEPENDENCIES: dict[str, list[str]] = {
    "sandbox": [],
    "claude_auth": ["sandbox"],
    "github_token": ["sandbox"],
    "orchestrator": [],
}

# Order in which checks should be executed.
# Dependencies must come before dependents.
CHECK_ORDER: list[str] = ["sandbox", "claude_auth", "github_token", "orchestrator"]

# Telemetry - uses no-op tracer/meter when OTLP not configured
_tracer = trace.get_tracer("orchestrator.health")
_meter = metrics.get_meter("orchestrator.health")

# Metrics for health checks
_health_check_counter = _meter.create_counter(
    "orchestrator_health_checks_total",
    description="Total health checks executed",
)
_health_check_duration = _meter.create_histogram(
    "orchestrator_health_check_duration_seconds",
    description="Health check execution duration",
    unit="s",
)


def check_sandbox(container_name: str = DEFAULT_CONTAINER) -> CheckResult:
    """Check if the sandbox container is running.

    Uses 'docker inspect' to verify the container exists and is running.

    Args:
        container_name: Name of the Docker container to check

    Returns:
        CheckResult with status "ok" if running, "failed" otherwise
    """
    with _tracer.start_as_current_span("health_check.sandbox") as span:
        span.set_attribute("container.name", container_name)
        start_time = time.monotonic()

        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Running}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=HEALTH_CHECK_TIMEOUT,
            )

            if result.returncode != 0:
                check_result = CheckResult(
                    status="failed",
                    message=f"Container '{container_name}' not found. "
                    "Run 'docker compose up -d' to start the sandbox.",
                    check_name="sandbox",
                )
            elif result.stdout.strip().lower() == "true":
                check_result = CheckResult(
                    status="ok",
                    message="Container running",
                    check_name="sandbox",
                )
            else:
                check_result = CheckResult(
                    status="failed",
                    message=f"Container '{container_name}' exists but is not running. "
                    "Run 'docker compose up -d' to start it.",
                    check_name="sandbox",
                )

        except subprocess.TimeoutExpired:
            check_result = CheckResult(
                status="failed",
                message="Docker command timed out. Is Docker running?",
                check_name="sandbox",
            )
        except FileNotFoundError:
            check_result = CheckResult(
                status="failed",
                message="Docker not found. Please install Docker.",
                check_name="sandbox",
            )

        # Record telemetry
        duration = time.monotonic() - start_time
        span.set_attribute("check.status", check_result.status)
        _health_check_counter.add(1, {"check": "sandbox", "status": check_result.status})
        _health_check_duration.record(duration, {"check": "sandbox"})

        return check_result


def check_claude_auth(container_name: str = DEFAULT_CONTAINER) -> CheckResult:
    """Check if Claude is authenticated in the sandbox.

    Runs 'claude --version' in the container to verify Claude CLI is available
    and properly configured. If it exits successfully, authentication is valid.

    Args:
        container_name: Name of the Docker container to check

    Returns:
        CheckResult with status "ok" if authenticated, "failed" otherwise
    """
    with _tracer.start_as_current_span("health_check.claude_auth") as span:
        span.set_attribute("container.name", container_name)
        start_time = time.monotonic()

        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-u",
                    "ubuntu",
                    container_name,
                    "claude",
                    "--version",
                ],
                capture_output=True,
                text=True,
                timeout=HEALTH_CHECK_TIMEOUT,
            )

            if result.returncode == 0:
                check_result = CheckResult(
                    status="ok",
                    message="Claude CLI authenticated",
                    check_name="claude_auth",
                )
            else:
                # Check for authentication-related error messages
                stderr = result.stderr.lower()
                if "not logged in" in stderr or "authenticate" in stderr:
                    check_result = CheckResult(
                        status="failed",
                        message="Claude not logged in. Run "
                        f"'docker exec -it {container_name} su - ubuntu -c \"claude login\"' "
                        "to authenticate.",
                        check_name="claude_auth",
                    )
                else:
                    check_result = CheckResult(
                        status="failed",
                        message=f"Claude CLI check failed: {result.stderr.strip()}",
                        check_name="claude_auth",
                    )

        except subprocess.TimeoutExpired:
            check_result = CheckResult(
                status="failed",
                message="Claude auth check timed out",
                check_name="claude_auth",
            )
        except FileNotFoundError:
            check_result = CheckResult(
                status="failed",
                message="Docker not found",
                check_name="claude_auth",
            )

        # Record telemetry
        duration = time.monotonic() - start_time
        span.set_attribute("check.status", check_result.status)
        _health_check_counter.add(
            1, {"check": "claude_auth", "status": check_result.status}
        )
        _health_check_duration.record(duration, {"check": "claude_auth"})

        return check_result


def check_github_token(container_name: str = DEFAULT_CONTAINER) -> CheckResult:
    """Check if GitHub token is configured in the sandbox.

    Checks if the GITHUB_TOKEN environment variable is set in the container.

    Args:
        container_name: Name of the Docker container to check

    Returns:
        CheckResult with status "ok" if token is set, "failed" otherwise
    """
    with _tracer.start_as_current_span("health_check.github_token") as span:
        span.set_attribute("container.name", container_name)
        start_time = time.monotonic()

        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-u",
                    "ubuntu",
                    container_name,
                    "bash",
                    "-c",
                    "test -n \"$GITHUB_TOKEN\" && echo 'set' || echo 'unset'",
                ],
                capture_output=True,
                text=True,
                timeout=HEALTH_CHECK_TIMEOUT,
            )

            if result.returncode == 0 and result.stdout.strip() == "set":
                check_result = CheckResult(
                    status="ok",
                    message="GitHub token configured",
                    check_name="github_token",
                )
            else:
                check_result = CheckResult(
                    status="failed",
                    message="GITHUB_TOKEN not set in sandbox. "
                    "Add it to your sandbox .env file or docker-compose.yml.",
                    check_name="github_token",
                )

        except subprocess.TimeoutExpired:
            check_result = CheckResult(
                status="failed",
                message="GitHub token check timed out",
                check_name="github_token",
            )
        except FileNotFoundError:
            check_result = CheckResult(
                status="failed",
                message="Docker not found",
                check_name="github_token",
            )

        # Record telemetry
        duration = time.monotonic() - start_time
        span.set_attribute("check.status", check_result.status)
        _health_check_counter.add(
            1, {"check": "github_token", "status": check_result.status}
        )
        _health_check_duration.record(duration, {"check": "github_token"})

        return check_result


def check_orchestrator() -> CheckResult:
    """Check if the orchestrator module is properly configured.

    Verifies that the orchestrator can import required modules and
    has valid configuration.

    Returns:
        CheckResult with status "ok" if configured, "failed" otherwise
    """
    with _tracer.start_as_current_span("health_check.orchestrator") as span:
        start_time = time.monotonic()

        try:
            # Verify we can import the essential orchestrator modules
            from orchestrator.config import OrchestratorConfig
            from orchestrator.sandbox import SandboxManager

            # Verify config can be created
            config = OrchestratorConfig.from_env()

            # Verify sandbox manager can be instantiated
            _ = SandboxManager(
                container_name=config.sandbox_container,
                workspace_path=config.workspace_path,
            )

            check_result = CheckResult(
                status="ok",
                message="Orchestrator configured",
                check_name="orchestrator",
            )

        except ImportError as e:
            check_result = CheckResult(
                status="failed",
                message=f"Failed to import orchestrator modules: {e}",
                check_name="orchestrator",
            )
        except Exception as e:
            check_result = CheckResult(
                status="failed",
                message=f"Orchestrator configuration error: {e}",
                check_name="orchestrator",
            )

        # Record telemetry
        duration = time.monotonic() - start_time
        span.set_attribute("check.status", check_result.status)
        _health_check_counter.add(
            1, {"check": "orchestrator", "status": check_result.status}
        )
        _health_check_duration.record(duration, {"check": "orchestrator"})

        return check_result


def get_health(
    container_name: str = DEFAULT_CONTAINER,
    checks: list[str] | None = None,
) -> HealthReport:
    """Run health checks and return an aggregated report.

    Runs checks in dependency order (as defined by CHECK_ORDER). If a check
    fails, all checks that depend on it are skipped with status "skipped".

    Args:
        container_name: Name of the Docker container to check
        checks: Optional list of specific checks to run. If None, runs all checks.

    Returns:
        HealthReport with overall status and individual check results
    """
    with _tracer.start_as_current_span("health_check") as span:
        start_time = time.monotonic()
        checks_to_run = set(checks) if checks else set(CHECK_ORDER)
        span.set_attribute("checks.requested", list(checks_to_run))
        results: dict[str, CheckResult] = {}

        for check_name in CHECK_ORDER:
            if check_name not in checks_to_run:
                continue

            # Check if any dependency failed
            dependencies = CHECK_DEPENDENCIES.get(check_name, [])
            dependency_failed = any(
                results.get(dep) and results[dep].status == "failed"
                for dep in dependencies
            )

            if dependency_failed:
                # Find which dependency failed for the message
                failed_dep = next(
                    dep
                    for dep in dependencies
                    if results.get(dep) and results[dep].status == "failed"
                )
                results[check_name] = CheckResult(
                    status="skipped",
                    message=f"Skipped because {failed_dep} check failed",
                    check_name=check_name,
                )
                # Record skipped check in metrics
                _health_check_counter.add(1, {"check": check_name, "status": "skipped"})
            else:
                # Run the check - call functions directly for testability
                if check_name == "sandbox":
                    results[check_name] = check_sandbox(container_name)
                elif check_name == "claude_auth":
                    results[check_name] = check_claude_auth(container_name)
                elif check_name == "github_token":
                    results[check_name] = check_github_token(container_name)
                elif check_name == "orchestrator":
                    results[check_name] = check_orchestrator()

        # Calculate overall status: unhealthy if any check failed or was skipped
        has_failure = any(
            result.status in ("failed", "skipped") for result in results.values()
        )
        overall_status: Literal["healthy", "unhealthy"] = (
            "unhealthy" if has_failure else "healthy"
        )

        # Record overall health check telemetry
        duration = time.monotonic() - start_time
        span.set_attribute("health.status", overall_status)
        span.set_attribute("health.checks_run", len(results))
        _health_check_duration.record(duration, {"check": "overall"})

        return HealthReport(
            status=overall_status,
            timestamp=datetime.utcnow(),
            checks=results,
        )
