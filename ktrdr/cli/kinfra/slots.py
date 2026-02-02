"""Slot container management for kinfra.

Provides utilities for starting and stopping containers with override files.
"""

import subprocess
import time

from ktrdr.cli.sandbox_registry import SlotInfo


def start_slot_containers(slot: SlotInfo, timeout: int = 120) -> None:
    """Start containers for a slot with override.

    Args:
        slot: Slot to start
        timeout: Max seconds to wait for health

    Raises:
        RuntimeError: If containers fail to start or health check fails
    """
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
        cmd, cwd=slot.infrastructure_path, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start containers: {result.stderr}")

    # Wait for health
    _wait_for_health(slot, timeout)


def stop_slot_containers(slot: SlotInfo) -> None:
    """Stop containers for a slot (keeps volumes).

    Args:
        slot: Slot to stop
    """
    cmd = ["docker", "compose", "down"]
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
