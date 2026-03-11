"""Slot container management for kinfra.

Provides utilities for starting and stopping containers with override files.
"""

import os
import subprocess
import time

from ktrdr.cli.sandbox_registry import SlotInfo


def _build_compose_env(slot: SlotInfo) -> dict[str, str]:
    """Build environment dict with secrets for Docker Compose.

    Merges OS env, .env.sandbox, and 1Password secrets in correct precedence.

    Args:
        slot: Slot with infrastructure_path containing .env.sandbox

    Returns:
        Environment dict ready for subprocess
    """
    from ktrdr.cli.kinfra.sandbox import fetch_sandbox_secrets, load_env_sandbox

    compose_env = os.environ.copy()

    # Load .env.sandbox from slot infrastructure dir
    env = load_env_sandbox(slot.infrastructure_path)
    compose_env.update(env)

    # Inject 1Password secrets (same flow as `sandbox up`)
    secrets_env = fetch_sandbox_secrets()
    compose_env.update(secrets_env)

    # Sandbox always uses development mode
    compose_env["KTRDR_ENV"] = "development"

    return compose_env


def reset_slot_volumes(slot: SlotInfo) -> None:
    """Remove containers and volumes for a slot to ensure clean state.

    Called before starting containers on a freshly claimed slot to prevent
    stale volume issues (e.g., PostgreSQL auth failures from old credentials).

    Args:
        slot: Slot to reset
    """
    cmd = [
        "docker",
        "compose",
        "--env-file",
        ".env.sandbox",
        "-f",
        "docker-compose.yml",
        "down",
        "-v",
    ]
    # Best-effort: if nothing is running, this is a no-op
    subprocess.run(
        cmd, cwd=slot.infrastructure_path, capture_output=True, text=True
    )


def start_slot_containers(slot: SlotInfo, timeout: int = 120) -> None:
    """Start containers for a slot with override.

    Injects 1Password secrets (same flow as `sandbox up`) and resets
    volumes to prevent stale credential issues.

    Args:
        slot: Slot to start
        timeout: Max seconds to wait for health

    Raises:
        RuntimeError: If containers fail to start or health check fails
    """
    # Reset volumes to prevent stale DB credentials
    reset_slot_volumes(slot)

    compose_env = _build_compose_env(slot)

    cmd = [
        "docker",
        "compose",
        "--env-file",
        ".env.sandbox",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.override.yml",
        "up",
        "-d",
    ]
    result = subprocess.run(
        cmd, cwd=slot.infrastructure_path, capture_output=True, text=True,
        env=compose_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start containers: {result.stderr}")

    # Wait for health
    _wait_for_health(slot, timeout)


def stop_slot_containers(slot: SlotInfo, remove_volumes: bool = False) -> None:
    """Stop containers for a slot.

    Args:
        slot: Slot to stop
        remove_volumes: If True, also remove volumes (clean slate for reuse)
    """
    cmd = ["docker", "compose", "down"]
    if remove_volumes:
        cmd.append("-v")
    subprocess.run(cmd, cwd=slot.infrastructure_path, check=True)


def _wait_for_health(slot: SlotInfo, timeout: int) -> None:
    """Wait for backend to be healthy.

    Args:
        slot: Slot with port information
        timeout: Max seconds to wait

    Raises:
        RuntimeError: If backend doesn't become healthy within timeout
    """
    import httpx

    url = f"http://localhost:{slot.ports['api']}/api/v1/health"
    start = time.time()

    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code == 200:
                return
        except httpx.RequestError:
            # Backend may not be reachable yet; ignore and retry until timeout.
            pass
        time.sleep(2)

    raise RuntimeError(f"Backend not healthy after {timeout}s")
