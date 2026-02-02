"""
Tests for the sandbox instance registry module.

This module tests instance tracking, slot allocation,
and registry persistence for sandbox management.
"""

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_registry_dir(tmp_path):
    """Create a temporary registry directory for testing."""
    registry_dir = tmp_path / ".ktrdr" / "sandbox"
    registry_dir.mkdir(parents=True)
    return registry_dir


@pytest.fixture
def mock_registry_path(temp_registry_dir):
    """Patch registry path to use temp directory."""
    registry_file = temp_registry_dir / "instances.json"
    with patch("ktrdr.cli.sandbox_registry.REGISTRY_DIR", temp_registry_dir):
        with patch("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_file):
            yield registry_file


class TestLoadRegistry:
    """Tests for loading the registry."""

    def test_load_empty_registry(self, mock_registry_path):
        """Returns empty registry when file doesn't exist."""
        from ktrdr.cli.sandbox_registry import REGISTRY_VERSION, load_registry

        registry = load_registry()

        assert registry.version == REGISTRY_VERSION  # v2 by default
        assert registry.instances == {}

    def test_load_existing_registry(self, mock_registry_path):
        """Loads existing registry from disk."""
        from ktrdr.cli.sandbox_registry import load_registry

        # Write a registry file
        data = {
            "version": 1,
            "instances": {
                "ktrdr--test": {
                    "instance_id": "ktrdr--test",
                    "slot": 1,
                    "path": "/tmp/ktrdr--test",
                    "created_at": "2024-01-15T10:30:00Z",
                    "is_worktree": True,
                    "parent_repo": "/tmp/ktrdr",
                }
            },
        }
        mock_registry_path.write_text(json.dumps(data))

        registry = load_registry()

        assert "ktrdr--test" in registry.instances
        assert registry.instances["ktrdr--test"].slot == 1

    def test_load_corrupted_registry_returns_empty(self, mock_registry_path):
        """Returns empty registry when file is corrupted."""
        from ktrdr.cli.sandbox_registry import REGISTRY_VERSION, load_registry

        mock_registry_path.write_text("not valid json {{{")

        registry = load_registry()

        assert registry.version == REGISTRY_VERSION  # v2 by default
        assert registry.instances == {}


class TestSaveRegistry:
    """Tests for saving the registry."""

    def test_save_creates_file(self, mock_registry_path):
        """Save creates registry file."""
        from ktrdr.cli.sandbox_registry import Registry, save_registry

        registry = Registry(version=1, instances={})
        save_registry(registry)

        assert mock_registry_path.exists()

    def test_save_writes_valid_json(self, mock_registry_path):
        """Saved file is valid JSON."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            Registry,
            save_registry,
        )

        info = InstanceInfo(
            instance_id="ktrdr--test",
            slot=1,
            path="/tmp/ktrdr--test",
            created_at="2024-01-15T10:30:00Z",
            is_worktree=True,
            parent_repo="/tmp/ktrdr",
        )
        registry = Registry(version=1, instances={"ktrdr--test": info})
        save_registry(registry)

        # Should be parseable JSON
        data = json.loads(mock_registry_path.read_text())
        assert data["version"] == 1
        assert "ktrdr--test" in data["instances"]


class TestAddInstance:
    """Tests for adding instances."""

    def test_add_and_get_instance(self, mock_registry_path):
        """Add instance, retrieve it."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            get_instance,
        )

        info = InstanceInfo(
            instance_id="ktrdr--feature-a",
            slot=2,
            path="/tmp/ktrdr--feature-a",
            created_at="2024-01-15T10:30:00Z",
            is_worktree=True,
            parent_repo="/tmp/ktrdr",
        )

        add_instance(info)
        retrieved = get_instance("ktrdr--feature-a")

        assert retrieved is not None
        assert retrieved.slot == 2
        assert retrieved.path == "/tmp/ktrdr--feature-a"

    def test_add_overwrites_existing(self, mock_registry_path):
        """Adding instance with same ID overwrites existing."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            get_instance,
        )

        info1 = InstanceInfo(
            instance_id="ktrdr--test",
            slot=1,
            path="/tmp/path1",
            created_at="2024-01-15T10:30:00Z",
            is_worktree=True,
        )
        info2 = InstanceInfo(
            instance_id="ktrdr--test",
            slot=3,
            path="/tmp/path2",
            created_at="2024-01-16T10:30:00Z",
            is_worktree=False,
        )

        add_instance(info1)
        add_instance(info2)

        retrieved = get_instance("ktrdr--test")
        assert retrieved.slot == 3
        assert retrieved.path == "/tmp/path2"


class TestRemoveInstance:
    """Tests for removing instances."""

    def test_remove_instance(self, mock_registry_path):
        """Remove instance, verify gone."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            get_instance,
            remove_instance,
        )

        info = InstanceInfo(
            instance_id="ktrdr--to-remove",
            slot=1,
            path="/tmp/ktrdr--to-remove",
            created_at="2024-01-15T10:30:00Z",
            is_worktree=True,
        )

        add_instance(info)
        assert get_instance("ktrdr--to-remove") is not None

        result = remove_instance("ktrdr--to-remove")

        assert result is True
        assert get_instance("ktrdr--to-remove") is None

    def test_remove_nonexistent_returns_false(self, mock_registry_path):
        """Removing nonexistent instance returns False."""
        from ktrdr.cli.sandbox_registry import remove_instance

        result = remove_instance("nonexistent-instance")

        assert result is False


class TestSlotAllocation:
    """Tests for slot allocation."""

    def test_allocate_next_slot_sequential(self, mock_registry_path):
        """Allocates 1, 2, 3 sequentially."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            allocate_next_slot,
        )

        # First allocation should be slot 1
        slot1 = allocate_next_slot()
        assert slot1 == 1

        # Add instance at slot 1
        add_instance(
            InstanceInfo(
                instance_id="test1",
                slot=1,
                path="/tmp/test1",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        # Second allocation should be slot 2
        slot2 = allocate_next_slot()
        assert slot2 == 2

    def test_allocate_next_slot_fills_gaps(self, mock_registry_path):
        """If slot 1 removed, next allocation is 1."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            allocate_next_slot,
            remove_instance,
        )

        # Add instances at slots 1 and 2
        add_instance(
            InstanceInfo(
                instance_id="test1",
                slot=1,
                path="/tmp/test1",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )
        add_instance(
            InstanceInfo(
                instance_id="test2",
                slot=2,
                path="/tmp/test2",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        # Remove slot 1
        remove_instance("test1")

        # Next allocation should fill the gap at slot 1
        next_slot = allocate_next_slot()
        assert next_slot == 1

    def test_all_slots_exhausted(self, mock_registry_path):
        """Raises after 10 allocations."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            allocate_next_slot,
        )

        # Fill all 10 slots
        for i in range(1, 11):
            add_instance(
                InstanceInfo(
                    instance_id=f"test{i}",
                    slot=i,
                    path=f"/tmp/test{i}",
                    created_at="2024-01-15T10:30:00Z",
                    is_worktree=True,
                )
            )

        # Next allocation should fail
        with pytest.raises(RuntimeError, match="All 10 sandbox slots are in use"):
            allocate_next_slot()

    def test_get_allocated_slots(self, mock_registry_path):
        """get_allocated_slots returns set of used slots."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            get_allocated_slots,
        )

        add_instance(
            InstanceInfo(
                instance_id="test1",
                slot=2,
                path="/tmp/test1",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )
        add_instance(
            InstanceInfo(
                instance_id="test2",
                slot=5,
                path="/tmp/test2",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        allocated = get_allocated_slots()

        assert allocated == {2, 5}


class TestStaleEntryCleanup:
    """Tests for cleaning stale entries."""

    def test_clean_stale_removes_missing_dirs(self, mock_registry_path, tmp_path):
        """Create entry, delete dir, clean removes it."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            clean_stale_entries,
            get_instance,
        )

        # Create a real directory
        real_dir = tmp_path / "ktrdr--real"
        real_dir.mkdir()

        # Add two instances: one with real dir, one with missing dir
        add_instance(
            InstanceInfo(
                instance_id="ktrdr--real",
                slot=1,
                path=str(real_dir),
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )
        add_instance(
            InstanceInfo(
                instance_id="ktrdr--missing",
                slot=2,
                path="/nonexistent/path/ktrdr--missing",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        # Clean stale entries
        removed = clean_stale_entries()

        # Should have removed the missing one
        assert "ktrdr--missing" in removed
        assert "ktrdr--real" not in removed

        # Verify state
        assert get_instance("ktrdr--real") is not None
        assert get_instance("ktrdr--missing") is None

    def test_clean_stale_returns_removed_ids(self, mock_registry_path):
        """clean_stale_entries returns list of removed instance IDs."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            clean_stale_entries,
        )

        # Add instance with nonexistent path
        add_instance(
            InstanceInfo(
                instance_id="stale1",
                slot=1,
                path="/nonexistent/stale1",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )
        add_instance(
            InstanceInfo(
                instance_id="stale2",
                slot=2,
                path="/nonexistent/stale2",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        removed = clean_stale_entries()

        assert set(removed) == {"stale1", "stale2"}


class TestRegistryPersistence:
    """Tests for registry persistence across load/save cycles."""

    def test_registry_persists_across_load(self, mock_registry_path):
        """Save, reload, verify data intact."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            load_registry,
        )

        # Add an instance
        add_instance(
            InstanceInfo(
                instance_id="persist-test",
                slot=3,
                path="/tmp/persist-test",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
                parent_repo="/tmp/ktrdr",
            )
        )

        # Reload registry (simulates new process)
        registry = load_registry()

        assert "persist-test" in registry.instances
        assert registry.instances["persist-test"].slot == 3
        assert registry.instances["persist-test"].parent_repo == "/tmp/ktrdr"


class TestLocalProdRegistry:
    """Tests for local-prod singleton CRUD operations."""

    def test_local_prod_not_exists_initially(self, mock_registry_path):
        """Empty registry has no local-prod."""
        from ktrdr.cli.sandbox_registry import local_prod_exists

        assert not local_prod_exists()

    def test_set_and_get_local_prod(self, mock_registry_path):
        """Set local-prod, retrieve it."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            get_local_prod,
            local_prod_exists,
            set_local_prod,
        )

        info = InstanceInfo(
            instance_id="ktrdr-prod",
            slot=0,
            path="/tmp/test-ktrdr-prod",
            created_at="2024-01-01T00:00:00Z",
            is_worktree=False,  # Clone, not worktree
            parent_repo=None,
        )
        set_local_prod(info)

        assert local_prod_exists()
        retrieved = get_local_prod()
        assert retrieved is not None
        assert retrieved.instance_id == "ktrdr-prod"
        assert retrieved.slot == 0
        assert not retrieved.is_worktree

    def test_clear_local_prod(self, mock_registry_path):
        """Clear local-prod removes it from registry."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            clear_local_prod,
            get_local_prod,
            local_prod_exists,
            set_local_prod,
        )

        # Set local-prod first
        info = InstanceInfo(
            instance_id="ktrdr-prod",
            slot=0,
            path="/tmp/test-ktrdr-prod",
            created_at="2024-01-01T00:00:00Z",
            is_worktree=False,
            parent_repo=None,
        )
        set_local_prod(info)
        assert local_prod_exists()

        # Clear it
        clear_local_prod()

        assert not local_prod_exists()
        assert get_local_prod() is None

    def test_local_prod_is_worktree_false_for_clones(self, mock_registry_path):
        """Verify is_worktree=False is preserved for clone-based local-prod."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            get_local_prod,
            set_local_prod,
        )

        info = InstanceInfo(
            instance_id="ktrdr-prod",
            slot=0,
            path="/home/user/ktrdr-prod",
            created_at="2024-01-15T10:30:00Z",
            is_worktree=False,  # Must be False for clones
            parent_repo=None,  # Clones have no parent
        )
        set_local_prod(info)

        retrieved = get_local_prod()
        assert retrieved is not None
        assert retrieved.is_worktree is False
        assert retrieved.parent_repo is None


# =============================================================================
# V2 Schema Tests (Slot Pool Infrastructure)
# =============================================================================


class TestSlotInfo:
    """Tests for SlotInfo dataclass."""

    def test_slot_info_creation(self):
        """SlotInfo can be created with required fields."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/home/user/.ktrdr/sandboxes/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )

        assert slot.slot_id == 1
        assert slot.profile == "light"
        assert slot.workers == {"backtest": 1, "training": 1}
        assert slot.ports["api"] == 8001
        assert slot.claimed_by is None
        assert slot.claimed_at is None
        assert slot.status == "stopped"

    def test_slot_info_to_dict(self):
        """SlotInfo.to_dict() serializes correctly."""
        from datetime import datetime
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/home/user/.ktrdr/sandboxes/slot-1"),
            profile="standard",
            workers={"backtest": 2, "training": 2},
            ports={"api": 8001, "db": 5433},
            claimed_by=Path("/home/user/worktrees/feature-x"),
            claimed_at=datetime(2024, 1, 15, 10, 30, 0),
            status="running",
        )

        data = slot.to_dict()

        assert data["infrastructure_path"] == "/home/user/.ktrdr/sandboxes/slot-1"
        assert data["profile"] == "standard"
        assert data["workers"] == {"backtest": 2, "training": 2}
        assert data["ports"] == {"api": 8001, "db": 5433}
        assert data["claimed_by"] == "/home/user/worktrees/feature-x"
        assert data["claimed_at"] == "2024-01-15T10:30:00"
        assert data["status"] == "running"


class TestRegistryV2Schema:
    """Tests for v2 registry schema."""

    def test_registry_v2_schema_structure(self, mock_registry_path):
        """New registry has v2 schema with slots."""
        from ktrdr.cli.sandbox_registry import load_registry, save_registry

        # Load empty registry (creates v2 by default)
        registry = load_registry()

        # Save and reload
        save_registry(registry)

        # Check file has v2 structure
        import json

        data = json.loads(mock_registry_path.read_text())
        assert data["version"] == 2
        assert "slots" in data

    def test_registry_has_slots_dict(self, mock_registry_path):
        """Registry has slots dict for slot management."""
        from ktrdr.cli.sandbox_registry import load_registry

        registry = load_registry()

        # Registry should have a slots attribute (empty by default)
        assert hasattr(registry, "slots")
        assert isinstance(registry.slots, dict)


class TestMigrationV1ToV2:
    """Tests for v1 to v2 migration."""

    def test_migration_v1_to_v2(self, mock_registry_path):
        """v1 registries migrate to v2 cleanly."""
        import json

        from ktrdr.cli.sandbox_registry import load_registry

        # Write a v1 registry file
        v1_data = {
            "version": 1,
            "local_prod": None,
            "instances": {
                "ktrdr--test": {
                    "instance_id": "ktrdr--test",
                    "slot": 1,
                    "path": "/tmp/ktrdr--test",
                    "created_at": "2024-01-15T10:30:00Z",
                    "is_worktree": True,
                    "parent_repo": "/tmp/ktrdr",
                }
            },
        }
        mock_registry_path.write_text(json.dumps(v1_data))

        # Load should migrate
        registry = load_registry()

        # Should be v2 now
        assert registry.version == 2
        # Should preserve instances
        assert "ktrdr--test" in registry.instances
        # Should have slots dict
        assert hasattr(registry, "slots")

    def test_migration_preserves_local_prod(self, mock_registry_path):
        """Migration preserves local_prod singleton."""
        import json

        from ktrdr.cli.sandbox_registry import load_registry

        v1_data = {
            "version": 1,
            "local_prod": {
                "instance_id": "ktrdr-prod",
                "slot": 0,
                "path": "/tmp/ktrdr-prod",
                "created_at": "2024-01-01T00:00:00Z",
                "is_worktree": False,
                "parent_repo": None,
            },
            "instances": {},
        }
        mock_registry_path.write_text(json.dumps(v1_data))

        registry = load_registry()

        assert registry.version == 2
        assert registry.local_prod is not None
        assert registry.local_prod.instance_id == "ktrdr-prod"


class TestSlotClaiming:
    """Tests for slot claim/release operations."""

    def test_get_available_slot_finds_unclaimed(self, mock_registry_path):
        """get_available_slot finds unclaimed slots."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()

        # Add a slot
        slot = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        registry.slots["1"] = slot
        save_registry(registry)

        # Reload and find available
        registry = load_registry()
        available = registry.get_available_slot()

        assert available is not None
        assert available.slot_id == 1

    def test_get_available_slot_with_profile(self, mock_registry_path):
        """get_available_slot respects profile requirement."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()

        # Add light and standard slots
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        registry.slots["5"] = SlotInfo(
            slot_id=5,
            infrastructure_path=Path("/tmp/slot-5"),
            profile="standard",
            workers={"backtest": 2, "training": 2},
            ports={"api": 8005, "db": 5437},
        )
        save_registry(registry)

        # Request standard profile
        registry = load_registry()
        available = registry.get_available_slot(min_profile="standard")

        assert available is not None
        assert available.profile == "standard"

    def test_get_available_slot_prefers_lower_profile(self, mock_registry_path):
        """get_available_slot prefers light over standard when both available."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()

        # Add standard slot first (slot 5)
        registry.slots["5"] = SlotInfo(
            slot_id=5,
            infrastructure_path=Path("/tmp/slot-5"),
            profile="standard",
            workers={"backtest": 2, "training": 2},
            ports={"api": 8005, "db": 5437},
        )
        # Add light slot second (slot 1)
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        save_registry(registry)

        # Request light profile (default)
        registry = load_registry()
        available = registry.get_available_slot(min_profile="light")

        # Should get the light slot, not standard
        assert available is not None
        assert available.profile == "light"
        assert available.slot_id == 1

    def test_claim_slot(self, mock_registry_path):
        """claim_slot updates claimed_by, claimed_at, status."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        save_registry(registry)

        # Claim the slot
        registry = load_registry()
        worktree_path = Path("/home/user/worktrees/feature-x")
        registry.claim_slot(1, worktree_path)

        # Reload and verify
        registry = load_registry()
        slot = registry.slots["1"]

        assert slot.claimed_by == worktree_path
        assert slot.claimed_at is not None
        assert slot.status == "running"

    def test_release_slot(self, mock_registry_path):
        """release_slot clears claim fields, sets status=stopped."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        save_registry(registry)

        # Claim then release
        registry = load_registry()
        registry.claim_slot(1, Path("/home/user/worktrees/feature-x"))
        registry.release_slot(1)

        # Reload and verify
        registry = load_registry()
        slot = registry.slots["1"]

        assert slot.claimed_by is None
        assert slot.claimed_at is None
        assert slot.status == "stopped"

    def test_get_available_slot_skips_claimed(self, mock_registry_path):
        """get_available_slot skips claimed slots."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()

        # Add two light slots
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        registry.slots["2"] = SlotInfo(
            slot_id=2,
            infrastructure_path=Path("/tmp/slot-2"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8002, "db": 5434},
        )
        save_registry(registry)

        # Claim slot 1
        registry = load_registry()
        registry.claim_slot(1, Path("/home/user/worktrees/feature-x"))

        # Get available should return slot 2
        registry = load_registry()
        available = registry.get_available_slot()

        assert available is not None
        assert available.slot_id == 2

    def test_get_available_slot_returns_none_when_all_claimed(self, mock_registry_path):
        """get_available_slot returns None when all matching slots claimed."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()

        # Add one slot and claim it
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        save_registry(registry)

        registry = load_registry()
        registry.claim_slot(1, Path("/home/user/worktrees/feature-x"))

        # Get available should return None
        registry = load_registry()
        available = registry.get_available_slot()

        assert available is None


class TestGetAllSlots:
    """Tests for get_all_slots method."""

    def test_get_all_slots(self, mock_registry_path):
        """get_all_slots returns all slots."""
        from pathlib import Path

        from ktrdr.cli.sandbox_registry import SlotInfo, load_registry, save_registry

        registry = load_registry()

        # Add multiple slots
        registry.slots["1"] = SlotInfo(
            slot_id=1,
            infrastructure_path=Path("/tmp/slot-1"),
            profile="light",
            workers={"backtest": 1, "training": 1},
            ports={"api": 8001, "db": 5433},
        )
        registry.slots["5"] = SlotInfo(
            slot_id=5,
            infrastructure_path=Path("/tmp/slot-5"),
            profile="standard",
            workers={"backtest": 2, "training": 2},
            ports={"api": 8005, "db": 5437},
        )
        save_registry(registry)

        # Reload and get all
        registry = load_registry()
        all_slots = registry.get_all_slots()

        assert len(all_slots) == 2
        assert "1" in all_slots
        assert "5" in all_slots

    def test_local_prod_singleton_overwrite(self, mock_registry_path):
        """Setting local-prod twice overwrites the previous one."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            get_local_prod,
            set_local_prod,
        )

        info1 = InstanceInfo(
            instance_id="ktrdr-prod-1",
            slot=0,
            path="/path/one",
            created_at="2024-01-01T00:00:00Z",
            is_worktree=False,
        )
        info2 = InstanceInfo(
            instance_id="ktrdr-prod-2",
            slot=0,
            path="/path/two",
            created_at="2024-01-02T00:00:00Z",
            is_worktree=False,
        )

        set_local_prod(info1)
        set_local_prod(info2)

        retrieved = get_local_prod()
        assert retrieved.instance_id == "ktrdr-prod-2"
        assert retrieved.path == "/path/two"

    def test_local_prod_persists_across_load(self, mock_registry_path):
        """Local-prod survives save/reload cycle."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            load_registry,
            set_local_prod,
        )

        info = InstanceInfo(
            instance_id="ktrdr-prod",
            slot=0,
            path="/tmp/ktrdr-prod",
            created_at="2024-01-01T00:00:00Z",
            is_worktree=False,
            parent_repo=None,
        )
        set_local_prod(info)

        # Reload (simulates new process)
        registry = load_registry()

        assert registry.local_prod is not None
        assert registry.local_prod.instance_id == "ktrdr-prod"
        assert registry.local_prod.slot == 0
        assert registry.local_prod.is_worktree is False

    def test_local_prod_independent_of_sandboxes(self, mock_registry_path):
        """Local-prod doesn't affect sandbox instances and vice versa."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            clear_local_prod,
            get_instance,
            get_local_prod,
            local_prod_exists,
            remove_instance,
            set_local_prod,
        )

        # Set up both local-prod and a sandbox
        local_prod_info = InstanceInfo(
            instance_id="ktrdr-prod",
            slot=0,
            path="/tmp/ktrdr-prod",
            created_at="2024-01-01T00:00:00Z",
            is_worktree=False,
        )
        sandbox_info = InstanceInfo(
            instance_id="ktrdr--feature-x",
            slot=1,
            path="/tmp/ktrdr--feature-x",
            created_at="2024-01-01T00:00:00Z",
            is_worktree=True,
            parent_repo="/tmp/ktrdr",
        )

        set_local_prod(local_prod_info)
        add_instance(sandbox_info)

        # Both should exist independently
        assert local_prod_exists()
        assert get_instance("ktrdr--feature-x") is not None

        # Removing sandbox doesn't affect local-prod
        remove_instance("ktrdr--feature-x")
        assert local_prod_exists()
        assert get_local_prod().instance_id == "ktrdr-prod"

        # Clearing local-prod doesn't affect sandboxes
        add_instance(sandbox_info)  # Re-add
        clear_local_prod()
        assert not local_prod_exists()
        assert get_instance("ktrdr--feature-x") is not None
