"""SSH utilities for KTRDR deployment.

This module provides functions to execute commands on remote
hosts with inline environment variable injection.
"""

import shlex
import subprocess
from pathlib import Path


class SSHError(Exception):
    """Raised when SSH operations fail."""

    pass


def scp_file(
    local_path: str | Path,
    host: str,
    remote_path: str,
    dry_run: bool = False,
) -> None:
    """
    Copy a file to a remote host via SCP.

    Args:
        local_path: Path to local file
        host: SSH host (e.g., 'backend.ktrdr.home.mynerd.place')
        remote_path: Destination path on remote host
        dry_run: If True, print command without executing

    Raises:
        SSHError: If SCP fails
        FileNotFoundError: If local file doesn't exist
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    scp_cmd = ["scp", str(local_path), f"{host}:{remote_path}"]

    if dry_run:
        print(f"[DRY RUN] Would execute: {' '.join(scp_cmd)}")
        return

    try:
        subprocess.run(
            scp_cmd,
            check=True,
            timeout=600,  # 10 minute timeout for large files
        )
    except subprocess.CalledProcessError as e:
        raise SSHError(f"SCP failed: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise SSHError("SCP timed out after 10 minutes") from e


def ssh_exec_with_env(
    host: str,
    workdir: str,
    env_vars: dict[str, str],
    command: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> str | None:
    """
    Execute command on remote host with inline environment variables.

    Args:
        host: SSH host (e.g., 'backend.ktrdr.home.mynerd.place')
        workdir: Working directory on remote host
        env_vars: Environment variables to inject
        command: Command to execute
        dry_run: If True, print command without executing
        verbose: If True, stream output in real-time (no capture)

    Returns:
        Command output if successful, None if dry_run or verbose

    Raises:
        SSHError: If SSH connection or command fails
    """
    # Build export statements for env vars (so they apply to all commands in chain)
    export_parts = [f"export {k}={shlex.quote(v)}" for k, v in env_vars.items()]
    export_string = "; ".join(export_parts)

    # Build full command with exports before the actual command
    if export_string:
        full_cmd = f"cd {shlex.quote(workdir)} && {export_string}; {command}"
    else:
        full_cmd = f"cd {shlex.quote(workdir)} && {command}"
    ssh_cmd = ["ssh", host, full_cmd]

    if dry_run:
        # Build masked export string (never include actual secret values in output)
        masked_parts = []
        for k, v in env_vars.items():
            # Mask values for keys that likely contain secrets
            is_secret = any(
                secret_key in k.upper()
                for secret_key in ["PASSWORD", "SECRET", "TOKEN"]
            )
            masked_parts.append(f"export {k}={'***' if is_secret else shlex.quote(v)}")
        masked_exports = "; ".join(masked_parts)
        if masked_exports:
            masked_cmd = f"cd {shlex.quote(workdir)} && {masked_exports}; {command}"
        else:
            masked_cmd = f"cd {shlex.quote(workdir)} && {command}"
        print(f"[DRY RUN] Would execute on {host}:")
        print(f"  {masked_cmd}")
        return None

    try:
        if verbose:
            # Stream output in real-time (for long-running commands like docker pull)
            subprocess.run(
                ssh_cmd,
                check=True,
                timeout=600,  # 10 minute timeout for verbose mode
            )
            return None
        else:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,  # 5 minute timeout
            )
            return result.stdout
    except subprocess.CalledProcessError as e:
        if verbose:
            raise SSHError("SSH command failed (see output above)") from e
        # Sanitize stderr to avoid exposing sensitive information
        stderr = e.stderr.strip() if e.stderr else "Unknown error"
        # Truncate long error messages
        if len(stderr) > 200:
            stderr = stderr[:200] + "..."
        raise SSHError(f"SSH command failed: {stderr}") from e
    except subprocess.TimeoutExpired as e:
        timeout = "10 minutes" if verbose else "5 minutes"
        raise SSHError(f"SSH command timed out after {timeout}") from e
