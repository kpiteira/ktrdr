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
        from ktrdr.cli.sandbox_registry import load_registry

        registry = load_registry()

        assert registry.version == 1
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
        from ktrdr.cli.sandbox_registry import load_registry

        mock_registry_path.write_text("not valid json {{{")

        registry = load_registry()

        assert registry.version == 1
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
