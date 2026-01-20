"""
Tests for sandbox edge case handling.

Tests for M7 edge case handling:
- Orphaned container detection
- Duplicate instance ID handling
- Improved slot exhaustion error messages
"""

from unittest.mock import MagicMock, patch

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


class TestOrphanedContainerDetection:
    """Tests for detecting orphaned Docker containers.

    Uses Docker's com.docker.compose.project label to get project names directly,
    avoiding container name parsing issues with multi-dash service names.
    """

    def test_detect_orphaned_containers_finds_unregistered(self, mock_registry_path):
        """Detects containers matching ktrdr-- pattern not in registry."""
        from ktrdr.cli.sandbox import detect_orphaned_containers
        from ktrdr.cli.sandbox_registry import InstanceInfo, add_instance

        # Add one registered instance
        add_instance(
            InstanceInfo(
                instance_id="ktrdr--registered",
                slot=1,
                path="/tmp/ktrdr--registered",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        # Mock docker ps to return project labels (not container names)
        # This simulates: docker ps --format '{{.Label "com.docker.compose.project"}}'
        mock_docker_output = "ktrdr--registered\nktrdr--orphaned\n"

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_docker_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            orphaned = detect_orphaned_containers()

        # Should find the orphaned one, not the registered one
        assert "ktrdr--orphaned" in orphaned
        assert "ktrdr--registered" not in orphaned

    def test_detect_orphaned_containers_empty_when_all_registered(
        self, mock_registry_path
    ):
        """Returns empty list when all containers are registered."""
        from ktrdr.cli.sandbox import detect_orphaned_containers
        from ktrdr.cli.sandbox_registry import InstanceInfo, add_instance

        # Register the instance
        add_instance(
            InstanceInfo(
                instance_id="ktrdr--test",
                slot=1,
                path="/tmp/ktrdr--test",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        # Mock docker ps with project label - same project appears multiple times
        # (once per container, but all with same project name)
        mock_docker_output = "ktrdr--test\nktrdr--test\n"

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_docker_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            orphaned = detect_orphaned_containers()

        assert orphaned == []

    def test_detect_orphaned_containers_handles_docker_failure(
        self, mock_registry_path
    ):
        """Returns empty list if docker command fails."""
        from ktrdr.cli.sandbox import detect_orphaned_containers

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Docker not available")

            orphaned = detect_orphaned_containers()

        assert orphaned == []

    def test_detect_orphaned_containers_handles_empty_output(self, mock_registry_path):
        """Returns empty list if no containers running."""
        from ktrdr.cli.sandbox import detect_orphaned_containers

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            orphaned = detect_orphaned_containers()

        assert orphaned == []

    def test_detect_orphaned_containers_ignores_non_ktrdr_containers(
        self, mock_registry_path
    ):
        """Ignores containers not matching ktrdr-- pattern."""
        from ktrdr.cli.sandbox import detect_orphaned_containers

        # Various non-matching project names
        mock_docker_output = (
            "postgres\n"
            "redis-main\n"
            "my-app\n"
            "ktrdr-not-sandbox\n"  # Missing double dash
        )

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_docker_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            orphaned = detect_orphaned_containers()

        assert orphaned == []

    def test_detect_orphaned_containers_handles_multi_dash_service_names(
        self, mock_registry_path
    ):
        """Handles projects with multi-dash names correctly.

        This test verifies that using Docker labels instead of parsing container
        names works correctly - the old rsplit approach would fail for services
        like 'backtest-worker-1' that have dashes in the name.
        """
        from ktrdr.cli.sandbox import detect_orphaned_containers
        from ktrdr.cli.sandbox_registry import InstanceInfo, add_instance

        # Register an instance with dashes in the name
        add_instance(
            InstanceInfo(
                instance_id="ktrdr--my-feature-branch",
                slot=1,
                path="/tmp/ktrdr--my-feature-branch",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        # Docker labels give us the exact project name regardless of service names
        mock_docker_output = "ktrdr--my-feature-branch\nktrdr--another-orphan\n"

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_docker_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            orphaned = detect_orphaned_containers()

        # Should correctly identify orphaned project
        assert "ktrdr--another-orphan" in orphaned
        assert "ktrdr--my-feature-branch" not in orphaned


class TestDuplicateInstanceIdHandling:
    """Tests for handling duplicate instance IDs."""

    def test_derive_unique_instance_id_returns_base_when_unused(
        self, mock_registry_path
    ):
        """Returns base ID when it's not in use."""
        from ktrdr.cli.sandbox import derive_unique_instance_id

        unique_id = derive_unique_instance_id("ktrdr--my-feature")

        assert unique_id == "ktrdr--my-feature"

    def test_derive_unique_instance_id_appends_number_when_taken(
        self, mock_registry_path
    ):
        """Appends -2 when base ID exists."""
        from ktrdr.cli.sandbox import derive_unique_instance_id
        from ktrdr.cli.sandbox_registry import InstanceInfo, add_instance

        # Register the base ID
        add_instance(
            InstanceInfo(
                instance_id="ktrdr--my-feature",
                slot=1,
                path="/tmp/ktrdr--my-feature",
                created_at="2024-01-15T10:30:00Z",
                is_worktree=True,
            )
        )

        unique_id = derive_unique_instance_id("ktrdr--my-feature")

        assert unique_id == "ktrdr--my-feature-2"

    def test_derive_unique_instance_id_increments_until_free(self, mock_registry_path):
        """Increments number until finding unused ID."""
        from ktrdr.cli.sandbox import derive_unique_instance_id
        from ktrdr.cli.sandbox_registry import InstanceInfo, add_instance

        # Register base and -2, -3 with different slots (realistic test data)
        suffixes_and_slots = [("", 1), ("-2", 2), ("-3", 3)]
        for suffix, slot in suffixes_and_slots:
            add_instance(
                InstanceInfo(
                    instance_id=f"ktrdr--feature{suffix}",
                    slot=slot,
                    path=f"/tmp/ktrdr--feature{suffix}",
                    created_at="2024-01-15T10:30:00Z",
                    is_worktree=True,
                )
            )

        unique_id = derive_unique_instance_id("ktrdr--feature")

        assert unique_id == "ktrdr--feature-4"


class TestSlotExhaustionMessage:
    """Tests for improved slot exhaustion error messages."""

    def test_allocate_next_slot_shows_all_instances_in_error(self, mock_registry_path):
        """Error message lists all instances when slots exhausted."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            allocate_next_slot,
        )

        # Fill all 10 slots
        for i in range(1, 11):
            add_instance(
                InstanceInfo(
                    instance_id=f"ktrdr--test-{i}",
                    slot=i,
                    path=f"/tmp/ktrdr--test-{i}",
                    created_at="2024-01-15T10:30:00Z",
                    is_worktree=True,
                )
            )

        # Should fail with helpful error listing all instances
        with pytest.raises(RuntimeError) as exc_info:
            allocate_next_slot()

        error_msg = str(exc_info.value)
        # Should mention all 10 slots are in use
        assert "All 10 sandbox slots are in use" in error_msg
        # Should list at least some instances
        assert "ktrdr--test-" in error_msg
        # Should suggest destroy command
        assert "destroy" in error_msg.lower()

    def test_allocate_next_slot_error_shows_slot_numbers(self, mock_registry_path):
        """Error message includes slot numbers for each instance."""
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            add_instance,
            allocate_next_slot,
        )

        # Fill all 10 slots
        for i in range(1, 11):
            add_instance(
                InstanceInfo(
                    instance_id=f"ktrdr--feature-{i}",
                    slot=i,
                    path=f"/tmp/ktrdr--feature-{i}",
                    created_at="2024-01-15T10:30:00Z",
                    is_worktree=True,
                )
            )

        with pytest.raises(RuntimeError) as exc_info:
            allocate_next_slot()

        error_msg = str(exc_info.value)
        # Should show slot number for at least one instance
        assert "Slot " in error_msg or "slot " in error_msg


class TestListInstancesOrphanWarning:
    """Tests for orphan warning in list command."""

    def test_list_instances_warns_about_orphans(self, mock_registry_path, runner):
        """list command warns when orphaned containers detected."""
        from ktrdr.cli import cli_app

        with patch("ktrdr.cli.sandbox.detect_orphaned_containers") as mock_detect:
            mock_detect.return_value = ["ktrdr--orphan-1", "ktrdr--orphan-2"]

            result = runner.invoke(cli_app, ["sandbox", "list"])

        # Should warn about orphans
        assert "orphan" in result.output.lower() or "Warning" in result.output

    def test_list_instances_no_warning_without_orphans(
        self, mock_registry_path, runner
    ):
        """list command doesn't warn when no orphans."""
        from ktrdr.cli import cli_app

        with patch("ktrdr.cli.sandbox.detect_orphaned_containers") as mock_detect:
            mock_detect.return_value = []

            result = runner.invoke(cli_app, ["sandbox", "list"])

        # Should not contain orphan warning
        output_lower = result.output.lower()
        # "orphan" should not appear in warning context (might be in help text)
        assert "found orphaned containers" not in output_lower
