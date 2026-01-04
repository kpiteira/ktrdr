"""Instance registry for sandbox management.

This module tracks sandbox instances in a JSON file at ~/.ktrdr/sandbox/instances.json.
It provides CRUD operations for instances and slot allocation logic.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

REGISTRY_DIR = Path.home() / ".ktrdr" / "sandbox"
REGISTRY_FILE = REGISTRY_DIR / "instances.json"


@dataclass
class InstanceInfo:
    """Information about a sandbox instance.

    Tracks the essential metadata needed to manage a sandbox instance:
    its identity, allocated port slot, filesystem path, and origin.
    """

    instance_id: str
    slot: int
    path: str
    created_at: str  # ISO format
    is_worktree: bool
    parent_repo: Optional[str] = None


@dataclass
class Registry:
    """Sandbox instance registry.

    Contains version info and a mapping of instance IDs to their metadata.
    """

    version: int = 1
    instances: dict[str, InstanceInfo] = field(default_factory=dict)


def _ensure_registry_dir() -> None:
    """Create registry directory if it doesn't exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def load_registry() -> Registry:
    """Load registry from disk, creating empty one if needed.

    Returns an empty registry if the file doesn't exist or is corrupted.
    This ensures the system degrades gracefully.
    """
    _ensure_registry_dir()
    if not REGISTRY_FILE.exists():
        return Registry()

    try:
        with open(REGISTRY_FILE) as f:
            data = json.load(f)
        instances = {k: InstanceInfo(**v) for k, v in data.get("instances", {}).items()}
        return Registry(version=data.get("version", 1), instances=instances)
    except (json.JSONDecodeError, TypeError, KeyError):
        # Corrupted file, start fresh
        return Registry()


def save_registry(registry: Registry) -> None:
    """Save registry to disk.

    Creates the registry directory if needed and writes the registry
    as formatted JSON for human readability.
    """
    _ensure_registry_dir()
    data = {
        "version": registry.version,
        "instances": {k: asdict(v) for k, v in registry.instances.items()},
    }
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_instance(info: InstanceInfo) -> None:
    """Add an instance to the registry.

    If an instance with the same ID exists, it will be overwritten.
    """
    registry = load_registry()
    registry.instances[info.instance_id] = info
    save_registry(registry)


def remove_instance(instance_id: str) -> bool:
    """Remove an instance from the registry.

    Returns:
        True if the instance was found and removed, False otherwise.
    """
    registry = load_registry()
    if instance_id in registry.instances:
        del registry.instances[instance_id]
        save_registry(registry)
        return True
    return False


def get_instance(instance_id: str) -> Optional[InstanceInfo]:
    """Get instance info by ID.

    Returns:
        InstanceInfo if found, None otherwise.
    """
    registry = load_registry()
    return registry.instances.get(instance_id)


def get_allocated_slots() -> set[int]:
    """Get set of currently allocated slots.

    Returns:
        Set of slot numbers (1-10) that are in use.
    """
    registry = load_registry()
    return {info.slot for info in registry.instances.values()}


def allocate_next_slot() -> int:
    """Allocate the next available slot (1-10).

    Fills gaps first - if slot 1 is freed, it will be reallocated
    before higher slots.

    Returns:
        The allocated slot number.

    Raises:
        RuntimeError: If all 10 slots are in use.
    """
    allocated = get_allocated_slots()
    for slot in range(1, 11):
        if slot not in allocated:
            return slot
    raise RuntimeError("All 10 sandbox slots are in use")


def clean_stale_entries() -> list[str]:
    """Remove entries where the directory no longer exists.

    This handles cases where directories were manually deleted
    without using `ktrdr sandbox destroy`.

    Returns:
        List of instance IDs that were removed.
    """
    registry = load_registry()
    stale = [
        instance_id
        for instance_id, info in registry.instances.items()
        if not Path(info.path).exists()
    ]
    for instance_id in stale:
        del registry.instances[instance_id]
    if stale:
        save_registry(registry)
    return stale
