"""Instance registry for sandbox management.

This module tracks sandbox instances in a JSON file at ~/.ktrdr/sandbox/instances.json.
It provides CRUD operations for instances and slot allocation logic.

V2 adds slot pool infrastructure with pre-defined slots, profiles, and claim/release.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

REGISTRY_DIR = Path.home() / ".ktrdr" / "sandbox"
REGISTRY_FILE = REGISTRY_DIR / "instances.json"

# Current registry version
REGISTRY_VERSION = 2

# Profile ordering for slot selection (prefer lower profiles)
PROFILE_ORDER = ["light", "standard", "heavy"]


@dataclass
class SlotInfo:
    """Information about a sandbox slot in the slot pool.

    Slots are pre-defined infrastructure directories that worktrees can
    claim temporarily. Each slot has a profile determining worker counts.
    """

    slot_id: int
    infrastructure_path: Path
    profile: str  # "light", "standard", "heavy"
    workers: dict[str, int]  # {"backtest": 1, "training": 1}
    ports: dict[str, int]  # {"api": 8001, "db": 5433, ...}
    claimed_by: Optional[Path] = None
    claimed_at: Optional[datetime] = None
    status: str = "stopped"  # "stopped", "running"

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "slot_id": self.slot_id,
            "infrastructure_path": str(self.infrastructure_path),
            "profile": self.profile,
            "workers": self.workers,
            "ports": self.ports,
            "claimed_by": str(self.claimed_by) if self.claimed_by else None,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SlotInfo":
        """Deserialize from dictionary."""
        claimed_at = None
        if data.get("claimed_at"):
            claimed_at = datetime.fromisoformat(data["claimed_at"])

        claimed_by = None
        if data.get("claimed_by"):
            claimed_by = Path(data["claimed_by"])

        return cls(
            slot_id=data["slot_id"],
            infrastructure_path=Path(data["infrastructure_path"]),
            profile=data["profile"],
            workers=data["workers"],
            ports=data["ports"],
            claimed_by=claimed_by,
            claimed_at=claimed_at,
            status=data.get("status", "stopped"),
        )


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

    V2 adds:
    - slots: Pre-defined slot pool with profiles and claim tracking

    The local_prod field is separate from instances because:
    - It's a singleton (only one allowed)
    - It uses slot 0 (reserved for standard ports)
    - It has different lifecycle (no slot allocation needed)
    """

    version: int = REGISTRY_VERSION
    local_prod: Optional[InstanceInfo] = None  # Singleton local-prod instance
    instances: dict[str, InstanceInfo] = field(default_factory=dict)  # Sandboxes only
    slots: dict[str, SlotInfo] = field(default_factory=dict)  # V2: Slot pool

    def get_available_slot(self, min_profile: str = "light") -> Optional[SlotInfo]:
        """Find an available slot with at least the requested profile.

        Prefers lower profiles when multiple slots match (light > standard > heavy).

        Args:
            min_profile: Minimum required profile ("light", "standard", "heavy")

        Returns:
            SlotInfo if available slot found, None otherwise
        """
        min_idx = PROFILE_ORDER.index(min_profile)

        # Sort slots by profile level (prefer lower) then by slot_id
        sorted_slots = sorted(
            self.slots.values(),
            key=lambda s: (PROFILE_ORDER.index(s.profile), s.slot_id),
        )

        for slot in sorted_slots:
            if slot.claimed_by is not None:
                continue
            profile_idx = PROFILE_ORDER.index(slot.profile)
            if profile_idx >= min_idx:
                return slot

        return None

    def claim_slot(self, slot_id: int, worktree_path: Path) -> None:
        """Claim a slot for a worktree.

        Args:
            slot_id: The slot ID to claim
            worktree_path: Path to the worktree claiming this slot
        """
        slot = self.slots[str(slot_id)]
        slot.claimed_by = worktree_path
        slot.claimed_at = datetime.now()
        slot.status = "running"
        self._save()

    def release_slot(self, slot_id: int) -> None:
        """Release a slot.

        Args:
            slot_id: The slot ID to release
        """
        slot = self.slots[str(slot_id)]
        slot.claimed_by = None
        slot.claimed_at = None
        slot.status = "stopped"
        self._save()

    def get_all_slots(self) -> dict[str, SlotInfo]:
        """Get all slots in the registry.

        Returns:
            Dictionary mapping slot ID strings to SlotInfo objects
        """
        return self.slots

    def _save(self) -> None:
        """Save this registry to disk."""
        save_registry(self)


def _ensure_registry_dir() -> None:
    """Create registry directory if it doesn't exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def load_registry() -> Registry:
    """Load registry from disk, creating empty one if needed.

    Returns an empty registry if the file doesn't exist or is corrupted.
    This ensures the system degrades gracefully.

    Automatically migrates v1 registries to v2.
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

        # Load slots (v2 feature)
        slots: dict[str, SlotInfo] = {}
        for slot_id, slot_data in data.get("slots", {}).items():
            slots[slot_id] = SlotInfo.from_dict(slot_data)

        registry = Registry(
            version=data.get("version", 1),
            local_prod=local_prod,
            instances=instances,
            slots=slots,
        )

        # Migrate v1 to v2 if needed
        if registry.version < REGISTRY_VERSION:
            registry = _migrate_to_v2(registry)
            save_registry(registry)

        return registry
    except (json.JSONDecodeError, TypeError, KeyError):
        # Corrupted file, start fresh
        return Registry()


def _migrate_to_v2(registry: Registry) -> Registry:
    """Migrate a v1 registry to v2 schema.

    Preserves all existing data (instances, local_prod) and adds
    empty slots dict. Actual slot provisioning is done by
    `kinfra sandbox provision`.

    Args:
        registry: The v1 registry to migrate

    Returns:
        Registry with v2 schema
    """
    return Registry(
        version=REGISTRY_VERSION,
        local_prod=registry.local_prod,
        instances=registry.instances,
        slots={},  # Slots will be provisioned separately
    )


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
        "slots": {k: v.to_dict() for k, v in registry.slots.items()},
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
