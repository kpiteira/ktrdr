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

    Contains version info, optional local_prod singleton, and a mapping of
    sandbox instance IDs to their metadata.

    The local_prod field is separate from instances because:
    - It's a singleton (only one allowed)
    - It uses slot 0 (reserved for standard ports)
    - It has different lifecycle (no slot allocation needed)
    """

    version: int = 1
    local_prod: Optional[InstanceInfo] = None  # Singleton local-prod instance
    instances: dict[str, InstanceInfo] = field(default_factory=dict)  # Sandboxes only


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

        # Load local_prod if present
        local_prod_data = data.get("local_prod")
        local_prod = InstanceInfo(**local_prod_data) if local_prod_data else None

        return Registry(
            version=data.get("version", 1),
            local_prod=local_prod,
            instances=instances,
        )
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
        "local_prod": asdict(registry.local_prod) if registry.local_prod else None,
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
        RuntimeError: If all 10 slots are in use. Error includes list of all instances.
    """
    allocated = get_allocated_slots()
    for slot in range(1, 11):
        if slot not in allocated:
            return slot

    # Provide helpful error with current allocations
    registry = load_registry()
    instances = sorted(registry.instances.items(), key=lambda x: x[1].slot)

    msg = "All 10 sandbox slots are in use:\n"
    for instance_id, info in instances:
        msg += f"  Slot {info.slot}: {instance_id}\n"
    msg += "\nDestroy unused instances with: ktrdr sandbox destroy"

    raise RuntimeError(msg)


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


# =============================================================================
# Local-prod singleton management
# =============================================================================


def local_prod_exists() -> bool:
    """Check if a local-prod instance is registered.

    Returns:
        True if local-prod exists in registry, False otherwise.
    """
    registry = load_registry()
    return registry.local_prod is not None


def get_local_prod() -> Optional[InstanceInfo]:
    """Get the local-prod instance info.

    Returns:
        InstanceInfo for local-prod if it exists, None otherwise.
    """
    registry = load_registry()
    return registry.local_prod


def set_local_prod(info: InstanceInfo) -> None:
    """Set the local-prod instance.

    Args:
        info: The InstanceInfo for the local-prod instance.
    """
    registry = load_registry()
    registry.local_prod = info
    save_registry(registry)


def clear_local_prod() -> None:
    """Clear the local-prod instance from the registry."""
    registry = load_registry()
    registry.local_prod = None
    save_registry(registry)
