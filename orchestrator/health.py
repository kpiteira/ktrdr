"""Health check module for orchestrator system readiness.

Provides health checks for sandbox container, Claude authentication,
GitHub token, and orchestrator state. Each check returns a CheckResult
with status and actionable message.
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from orchestrator.config import OrchestratorConfig


@dataclass
class CheckResult:
    """Result of a single health check.

    Attributes:
        status: Check result - "ok", "failed", or "skipped"
        message: Human-readable message explaining the status
        check_name: Name of the check that produced this result
    """

    status: Literal["ok", "failed", "skipped"]
    message: str
    check_name: str


@dataclass
class HealthReport:
    """Aggregated health report from all checks.

    Attributes:
        status: Overall status - "healthy" if all checks pass, "unhealthy" otherwise
        timestamp: When the health check was performed
        checks: Map of check name to CheckResult
    """

    status: Literal["healthy", "unhealthy"]
    timestamp: datetime
    checks: dict[str, CheckResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict.

        Returns:
            Dictionary with status, ISO timestamp, and check results
        """
        return {
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "checks": {
                name: {"status": r.status, "message": r.message}
                for name, r in self.checks.items()
            },
        }


# Check dependencies - which checks must pass before others can run
CHECK_DEPENDENCIES: dict[str, list[str]] = {
    "sandbox": [],
    "claude_auth": ["sandbox"],
    "github_token": ["sandbox"],
    "orchestrator": [],
}

# Order in which checks should be executed
CHECK_ORDER: list[str] = ["sandbox", "claude_auth", "github_token", "orchestrator"]

# Default timeout for subprocess commands
DEFAULT_TIMEOUT = 5


def check_sandbox(timeout: float = DEFAULT_TIMEOUT) -> CheckResult:
    """Check if sandbox container is running.

    Uses docker inspect to verify the container exists and is running.

    Args:
        timeout: Maximum seconds to wait for docker command

    Returns:
        CheckResult with status and message
    """
    config = OrchestratorConfig.from_env()
    container_name = config.sandbox_container

    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            return CheckResult(
                status="failed",
                message="container not running - run 'sandbox-init.sh'",
                check_name="sandbox",
            )

        is_running = result.stdout.strip().lower() == "true"
        if is_running:
            return CheckResult(
                status="ok",
                message="container running",
                check_name="sandbox",
            )
        else:
            return CheckResult(
                status="failed",
                message="container not running - run 'sandbox-init.sh'",
                check_name="sandbox",
            )

    except subprocess.TimeoutExpired:
        return CheckResult(
            status="failed",
            message=f"check timed out after {timeout}s",
            check_name="sandbox",
        )
    except FileNotFoundError:
        return CheckResult(
            status="failed",
            message="docker not available",
            check_name="sandbox",
        )


def check_claude_auth(timeout: float = DEFAULT_TIMEOUT) -> CheckResult:
    """Check if Claude is authenticated in sandbox.

    Checks for credentials.json in both /home/ubuntu/.claude/ and /root/.claude/
    directories inside the container.

    Args:
        timeout: Maximum seconds to wait for docker command

    Returns:
        CheckResult with status and message
    """
    config = OrchestratorConfig.from_env()
    container_name = config.sandbox_container

    # Check both possible locations for credentials
    check_cmd = (
        "test -f /home/ubuntu/.claude/credentials.json || "
        "test -f /root/.claude/credentials.json"
    )

    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c", check_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return CheckResult(
                status="ok",
                message="authenticated",
                check_name="claude_auth",
            )
        else:
            return CheckResult(
                status="failed",
                message="not logged in - run 'claude login' in sandbox",
                check_name="claude_auth",
            )

    except subprocess.TimeoutExpired:
        return CheckResult(
            status="failed",
            message=f"check timed out after {timeout}s",
            check_name="claude_auth",
        )
    except FileNotFoundError:
        return CheckResult(
            status="failed",
            message="docker not available",
            check_name="claude_auth",
        )


def check_github_token(timeout: float = DEFAULT_TIMEOUT) -> CheckResult:
    """Check if GH_TOKEN is present in sandbox.

    Verifies the GH_TOKEN environment variable is set and non-empty.

    Args:
        timeout: Maximum seconds to wait for docker command

    Returns:
        CheckResult with status and message
    """
    config = OrchestratorConfig.from_env()
    container_name = config.sandbox_container

    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c", 'test -n "$GH_TOKEN"'],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return CheckResult(
                status="ok",
                message="present",
                check_name="github_token",
            )
        else:
            return CheckResult(
                status="failed",
                message="GH_TOKEN not set - check sandbox environment",
                check_name="github_token",
            )

    except subprocess.TimeoutExpired:
        return CheckResult(
            status="failed",
            message=f"check timed out after {timeout}s",
            check_name="github_token",
        )
    except FileNotFoundError:
        return CheckResult(
            status="failed",
            message="docker not available",
            check_name="github_token",
        )


def check_orchestrator() -> CheckResult:
    """Check orchestrator state.

    Reads local state files to determine if orchestrator is idle or working.
    Does not depend on sandbox being available.

    Returns:
        CheckResult with status and current state message
    """
    config = OrchestratorConfig.from_env()
    state_dir = config.state_dir

    # Look for any active state files
    if not state_dir.exists():
        return CheckResult(
            status="ok",
            message="idle",
            check_name="orchestrator",
        )

    # Find state files
    state_files = list(state_dir.glob("*_state.json"))
    if not state_files:
        return CheckResult(
            status="ok",
            message="idle",
            check_name="orchestrator",
        )

    # If there are state files, try to read the most recent one
    # Import here to avoid circular imports
    from orchestrator.state import OrchestratorState

    # Get the most recently modified state file
    latest_state_file = max(state_files, key=lambda f: f.stat().st_mtime)
    milestone_id = latest_state_file.stem.replace("_state", "")

    state = OrchestratorState.load(state_dir, milestone_id)
    if state is None:
        return CheckResult(
            status="ok",
            message="idle",
            check_name="orchestrator",
        )

    # Determine the current task index
    next_task_index = state.get_next_task_index()
    # Task IDs are typically like "1.1", "1.2", etc.
    # The current_task_index is the index of the next task to run
    return CheckResult(
        status="ok",
        message=f"working on {state.milestone_id} (task {next_task_index + 1})",
        check_name="orchestrator",
    )
