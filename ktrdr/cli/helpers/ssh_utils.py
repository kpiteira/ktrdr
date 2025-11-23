"""SSH utilities for KTRDR deployment.

This module provides functions to execute commands on remote
hosts with inline environment variable injection.
"""

import shlex
import subprocess


class SSHError(Exception):
    """Raised when SSH operations fail."""

    pass


def ssh_exec_with_env(
    host: str,
    workdir: str,
    env_vars: dict[str, str],
    command: str,
    dry_run: bool = False,
) -> str | None:
    """
    Execute command on remote host with inline environment variables.

    Args:
        host: SSH host (e.g., 'backend.ktrdr.home.mynerd.place')
        workdir: Working directory on remote host
        env_vars: Environment variables to inject
        command: Command to execute
        dry_run: If True, print command without executing

    Returns:
        Command output if successful, None if dry_run

    Raises:
        SSHError: If SSH connection or command fails
    """
    # Build env string with proper quoting
    env_parts = [f"{k}={shlex.quote(v)}" for k, v in env_vars.items()]
    env_string = " ".join(env_parts)

    # Build full command with proper quoting for workdir
    full_cmd = f"cd {shlex.quote(workdir)} && {env_string} {command}"
    ssh_cmd = ["ssh", host, full_cmd]

    if dry_run:
        # Build masked env string directly (never include actual secret values in output)
        masked_parts = []
        for k, v in env_vars.items():
            # Mask values for keys that likely contain secrets
            is_secret = any(
                secret_key in k.upper()
                for secret_key in ["PASSWORD", "SECRET", "TOKEN"]
            )
            masked_parts.append(f"{k}={'***' if is_secret else shlex.quote(v)}")
        masked_env = " ".join(masked_parts)
        masked_cmd = f"cd {shlex.quote(workdir)} && {masked_env} {command}"
        print(f"[DRY RUN] Would execute on {host}:")
        print(f"  {masked_cmd}")
        return None

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minute timeout
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        # Sanitize stderr to avoid exposing sensitive information
        stderr = e.stderr.strip() if e.stderr else "Unknown error"
        # Truncate long error messages
        if len(stderr) > 200:
            stderr = stderr[:200] + "..."
        raise SSHError(f"SSH command failed: {stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise SSHError("SSH command timed out after 5 minutes") from e
