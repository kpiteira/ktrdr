"""Docker utilities for KTRDR deployment.

This module provides functions to manage Docker operations
on remote hosts, particularly GHCR authentication.
"""

import subprocess


class DockerError(Exception):
    """Raised when Docker operations fail."""

    pass


def docker_login_ghcr(
    host: str,
    username: str,
    token: str,
    dry_run: bool = False,
) -> bool:
    """
    Log in to GitHub Container Registry on remote host.

    Args:
        host: SSH host to run Docker login on
        username: GitHub username
        token: GitHub PAT with read:packages scope
        dry_run: If True, print command without executing

    Returns:
        True if login successful

    Raises:
        DockerError: If Docker login fails
    """
    # Build docker login command with password via stdin
    docker_cmd = f"echo '{token}' | docker login ghcr.io -u {username} --password-stdin"
    ssh_cmd = ["ssh", host, docker_cmd]

    if dry_run:
        # Mask token in output
        masked_cmd = docker_cmd.replace(token, "***")
        print(f"[DRY RUN] Would execute on {host}:")
        print(f"  {masked_cmd}")
        return True

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise DockerError(f"Docker login failed: {result.stderr}")

        return True
    except subprocess.CalledProcessError as e:
        raise DockerError(f"Docker login failed: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise DockerError("Docker login timed out") from e
