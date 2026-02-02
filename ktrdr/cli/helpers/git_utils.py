"""Git utilities for KTRDR deployment.

This module provides functions to interact with git for
deployment operations like getting the current commit SHA.
"""

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when git operations fail."""

    pass


def is_ktrdr_repo(path: Path) -> bool:
    """Check if path is a KTRDR repository by checking git remote.

    Args:
        path: The path to check.

    Returns:
        True if the git remote contains 'ktrdr', False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=path,
        )
        if result.returncode != 0:
            return False
        # Check if remote contains "ktrdr" (case-insensitive)
        return "ktrdr" in result.stdout.lower()
    except Exception:
        return False


def get_latest_sha_tag() -> str:
    """
    Get current git SHA formatted as image tag.

    Returns:
        Tag string like 'sha-a1b2c3d'

    Raises:
        GitError: If not in git repo or git fails
    """
    try:
        cmd = ["git", "rev-parse", "--short", "HEAD"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        sha = result.stdout.strip()
        return f"sha-{sha}"
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git error: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("Git not installed") from e
