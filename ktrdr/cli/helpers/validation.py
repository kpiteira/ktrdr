"""Pre-deployment validation for KTRDR deployment.

This module provides functions to validate all prerequisites
before attempting a deployment operation.
"""

import socket
import subprocess


def validate_deployment_prerequisites(host: str) -> tuple[bool, list[str]]:
    """
    Validate all prerequisites for deployment.

    Args:
        host: Target host for deployment

    Returns:
        Tuple of (success, errors) where success is True if all checks pass
        and errors is a list of error messages for failed checks
    """
    errors = []

    # Check DNS resolution
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        errors.append(f"DNS resolution failed for {host}")

    # Check SSH connectivity
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", host, "echo", "ok"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append(f"SSH connection failed to {host}")
    except subprocess.TimeoutExpired:
        errors.append(f"SSH connection timed out to {host}")

    # Check Docker on remote
    try:
        result = subprocess.run(
            ["ssh", host, "docker", "--version"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append(f"Docker not available on {host}")
    except subprocess.TimeoutExpired:
        errors.append(f"Docker check timed out on {host}")

    # Check op CLI locally
    try:
        result = subprocess.run(["op", "--version"], capture_output=True)
        if result.returncode != 0:
            errors.append("1Password CLI (op) not installed")
    except FileNotFoundError:
        errors.append("1Password CLI (op) not installed")

    # Check op authenticated
    try:
        result = subprocess.run(["op", "account", "list"], capture_output=True)
        if result.returncode != 0:
            errors.append("1Password CLI not authenticated (run: op signin)")
    except FileNotFoundError:
        pass  # Already caught above

    return (len(errors) == 0, errors)
