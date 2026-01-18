"""Environment validation for orchestrator prerequisites.

Validates that the orchestrator is running in a valid context:
- From the repository root
- With sandbox initialized
- With sandbox running
"""

import subprocess
from pathlib import Path

from orchestrator.errors import OrchestratorError


def validate_environment() -> Path:
    """Validate orchestrator prerequisites and return the code folder path.

    Checks three prerequisites:
    1. Running from repo root (.git directory exists)
    2. Sandbox initialized (.env.sandbox file exists)
    3. Sandbox running (ktrdr sandbox status shows running)

    Returns:
        Path to the current working directory (code folder) on success.

    Raises:
        OrchestratorError: If any prerequisite is not met. The error message
            includes an actionable command to fix the issue.
    """
    cwd = Path.cwd()

    # Check 1: Running from repo root
    if not (cwd / ".git").is_dir():
        raise OrchestratorError(
            "Not running from repository root. "
            "Please cd to the repo root directory (where .git exists)."
        )

    # Check 2: Sandbox initialized
    if not (cwd / ".env.sandbox").exists():
        raise OrchestratorError(
            "Sandbox not initialized. Run: ktrdr sandbox init"
        )

    # Check 3: Sandbox running
    try:
        result = subprocess.run(
            ["uv", "run", "ktrdr", "sandbox", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Check if running - look for "running" in output (case-insensitive)
        if result.returncode != 0 or "running" not in result.stdout.lower():
            raise OrchestratorError(
                "Sandbox not running. Run: ktrdr sandbox up"
            )

    except subprocess.TimeoutExpired as e:
        raise OrchestratorError(
            "Sandbox status check timed out. Run: ktrdr sandbox up"
        ) from e
    except FileNotFoundError as e:
        raise OrchestratorError(
            "uv command not found. Ensure uv is installed and in PATH."
        ) from e

    return cwd
