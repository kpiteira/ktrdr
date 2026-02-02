"""Tests for kinfra override file generator.

Tests the docker-compose.override.yml generation that mounts worktree code
into slot containers.
"""

from pathlib import Path
from unittest.mock import MagicMock

import yaml


class TestOverrideContainsWorktreePath:
    """Tests that override file contains worktree path."""

    def test_override_contains_worktree_path(self, tmp_path: Path) -> None:
        """Override should contain worktree path in volume mounts."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        assert override_file.exists()

        content = override_file.read_text()
        assert "/path/to/worktree/ktrdr" in content
        assert "/path/to/worktree/research_agents" in content


class TestOverrideValidYaml:
    """Tests that override generates valid YAML."""

    def test_override_valid_yaml(self, tmp_path: Path) -> None:
        """Override should generate valid YAML syntax."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()

        # Should parse as valid YAML
        # Note: ${VAR} syntax is valid YAML but won't be substituted by yaml.safe_load
        parsed = yaml.safe_load(content)
        assert parsed is not None
        assert "services" in parsed


class TestOverrideAllServices:
    """Tests that override includes all required services."""

    def test_override_includes_backend(self, tmp_path: Path) -> None:
        """Override should include backend service."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()
        parsed = yaml.safe_load(content)

        assert "backend" in parsed["services"]
        assert "volumes" in parsed["services"]["backend"]

    def test_override_includes_backtest_worker(self, tmp_path: Path) -> None:
        """Override should include backtest-worker service."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()
        parsed = yaml.safe_load(content)

        assert "backtest-worker" in parsed["services"]
        assert "volumes" in parsed["services"]["backtest-worker"]

    def test_override_includes_training_worker(self, tmp_path: Path) -> None:
        """Override should include training-worker service."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()
        parsed = yaml.safe_load(content)

        assert "training-worker" in parsed["services"]
        assert "volumes" in parsed["services"]["training-worker"]


class TestOverrideHasTimestamp:
    """Tests that override includes timestamp in header."""

    def test_override_has_timestamp(self, tmp_path: Path) -> None:
        """Override should include generation timestamp in header."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()

        assert "Generated at:" in content
        # Should have ISO format timestamp
        assert "202" in content  # Year prefix


class TestRemoveOverride:
    """Tests for override file removal."""

    def test_remove_override(self, tmp_path: Path) -> None:
        """remove_override should delete the override file."""
        from ktrdr.cli.kinfra.override import generate_override, remove_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        # Generate first
        generate_override(slot, worktree_path)
        override_file = tmp_path / "docker-compose.override.yml"
        assert override_file.exists()

        # Remove
        remove_override(slot)
        assert not override_file.exists()

    def test_remove_override_nonexistent(self, tmp_path: Path) -> None:
        """remove_override should not error if file doesn't exist."""
        from ktrdr.cli.kinfra.override import remove_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        # Should not raise
        remove_override(slot)


class TestOverrideSharedDirs:
    """Tests that override includes shared data directory mounts."""

    def test_override_includes_data_dir(self, tmp_path: Path) -> None:
        """Override should mount shared data directory from main repo."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")
        main_repo_path = Path("/path/to/main-repo")

        generate_override(slot, worktree_path, main_repo_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()

        assert "/path/to/main-repo/data:/app/data" in content

    def test_override_includes_models_dir(self, tmp_path: Path) -> None:
        """Override should mount shared models directory from main repo."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")
        main_repo_path = Path("/path/to/main-repo")

        generate_override(slot, worktree_path, main_repo_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()

        assert "/path/to/main-repo/models:/app/models" in content

    def test_override_includes_strategies_dir(self, tmp_path: Path) -> None:
        """Override should mount shared strategies directory from main repo."""
        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")
        main_repo_path = Path("/path/to/main-repo")

        generate_override(slot, worktree_path, main_repo_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()

        assert "/path/to/main-repo/strategies:/app/strategies" in content

    def test_override_defaults_main_repo_to_cwd(self, tmp_path: Path) -> None:
        """Override should default main_repo_path to cwd if not provided."""
        import os

        from ktrdr.cli.kinfra.override import generate_override
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        worktree_path = Path("/path/to/worktree")

        generate_override(slot, worktree_path)

        override_file = tmp_path / "docker-compose.override.yml"
        content = override_file.read_text()

        # Should contain cwd/data, cwd/models, cwd/strategies
        cwd = os.getcwd()
        assert f"{cwd}/data:/app/data" in content
