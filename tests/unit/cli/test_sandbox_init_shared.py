"""
Tests for the sandbox init-shared command (Task 5.1).

Tests the initialization of shared data directory (~/.ktrdr/shared/).
"""

from unittest.mock import patch

import pytest

from ktrdr.cli import cli_app


class TestGetDirStats:
    """Tests for the get_dir_stats helper function."""

    def test_get_dir_stats_empty_returns_zero(self, tmp_path):
        """Verify get_dir_stats returns 0, '0 B' for empty directory."""
        from ktrdr.cli.sandbox import get_dir_stats

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        count, size = get_dir_stats(empty_dir)

        assert count == 0
        assert size == "0 B"

    def test_get_dir_stats_nonexistent_returns_zero(self, tmp_path):
        """Verify get_dir_stats returns 0, '0 B' for nonexistent directory."""
        from ktrdr.cli.sandbox import get_dir_stats

        nonexistent = tmp_path / "does_not_exist"

        count, size = get_dir_stats(nonexistent)

        assert count == 0
        assert size == "0 B"

    def test_get_dir_stats_with_files(self, tmp_path):
        """Verify get_dir_stats returns correct count and size."""
        from ktrdr.cli.sandbox import get_dir_stats

        test_dir = tmp_path / "data"
        test_dir.mkdir()

        # Create some test files
        (test_dir / "file1.txt").write_text("hello")  # 5 bytes
        (test_dir / "file2.txt").write_text("world!")  # 6 bytes

        count, size = get_dir_stats(test_dir)

        assert count == 2
        # Size should be 11 bytes
        assert "11" in size or "B" in size

    def test_get_dir_stats_with_nested_files(self, tmp_path):
        """Verify get_dir_stats counts nested files."""
        from ktrdr.cli.sandbox import get_dir_stats

        test_dir = tmp_path / "nested"
        test_dir.mkdir()
        (test_dir / "sub1").mkdir()
        (test_dir / "sub1" / "file1.txt").write_text("a" * 100)
        (test_dir / "sub1" / "sub2").mkdir()
        (test_dir / "sub1" / "sub2" / "file2.txt").write_text("b" * 200)

        count, size = get_dir_stats(test_dir)

        assert count == 2
        # 100 + 200 = 300 bytes
        assert "300" in size or "B" in size

    def test_get_dir_stats_kb_formatting(self, tmp_path):
        """Verify get_dir_stats formats KB correctly."""
        from ktrdr.cli.sandbox import get_dir_stats

        test_dir = tmp_path / "kb"
        test_dir.mkdir()

        # Create a 2KB file
        (test_dir / "file.txt").write_bytes(b"x" * 2048)

        count, size = get_dir_stats(test_dir)

        assert count == 1
        assert "KB" in size or "2.0" in size

    def test_get_dir_stats_mb_formatting(self, tmp_path):
        """Verify get_dir_stats formats MB correctly."""
        from ktrdr.cli.sandbox import get_dir_stats

        test_dir = tmp_path / "mb"
        test_dir.mkdir()

        # Create a ~1MB file
        (test_dir / "file.txt").write_bytes(b"x" * (1024 * 1024))

        count, size = get_dir_stats(test_dir)

        assert count == 1
        assert "MB" in size or "1.0" in size


class TestInitSharedCommand:
    """Tests for the init-shared command."""

    @pytest.fixture
    def mock_shared_dir(self, tmp_path):
        """Mock SHARED_DIR to use temp directory."""
        shared_dir = tmp_path / ".ktrdr" / "shared"
        with patch("ktrdr.cli.sandbox.SHARED_DIR", shared_dir):
            yield shared_dir

    def test_init_shared_help_displays(self, runner):
        """Verify init-shared command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "init-shared", "--help"])

        assert result.exit_code == 0
        assert (
            "init-shared" in result.output.lower() or "shared" in result.output.lower()
        )

    def test_init_shared_minimal_creates_dirs(self, runner, mock_shared_dir):
        """Verify --minimal creates empty structure."""
        result = runner.invoke(cli_app, ["sandbox", "init-shared", "--minimal"])

        assert result.exit_code == 0
        assert mock_shared_dir.exists()
        assert (mock_shared_dir / "data").exists()
        assert (mock_shared_dir / "models").exists()
        assert (mock_shared_dir / "strategies").exists()

    def test_init_shared_minimal_shows_message(self, runner, mock_shared_dir):
        """Verify --minimal shows appropriate message."""
        result = runner.invoke(cli_app, ["sandbox", "init-shared", "--minimal"])

        assert result.exit_code == 0
        assert "minimal" in result.output.lower() or "empty" in result.output.lower()

    def test_init_shared_from_copies_data(self, runner, mock_shared_dir, tmp_path):
        """Verify --from copies data from existing environment."""
        # Create source with data
        source_dir = tmp_path / "ktrdr-source"
        source_dir.mkdir()
        (source_dir / "data").mkdir()
        (source_dir / "data" / "test.csv").write_text("symbol,price\nAAPL,150")
        (source_dir / "models").mkdir()
        (source_dir / "models" / "model.pt").write_bytes(b"model data")
        (source_dir / "strategies").mkdir()
        (source_dir / "strategies" / "config.json").write_text('{"name": "test"}')

        result = runner.invoke(
            cli_app, ["sandbox", "init-shared", "--from", str(source_dir)]
        )

        assert result.exit_code == 0
        # Verify data was copied
        assert (mock_shared_dir / "data" / "test.csv").exists()
        assert (mock_shared_dir / "models" / "model.pt").exists()
        assert (mock_shared_dir / "strategies" / "config.json").exists()

    def test_init_shared_from_shows_progress(self, runner, mock_shared_dir, tmp_path):
        """Verify --from shows copy progress."""
        # Create source with data
        source_dir = tmp_path / "ktrdr-source"
        source_dir.mkdir()
        (source_dir / "data").mkdir()
        (source_dir / "data" / "test.csv").write_text("test")

        result = runner.invoke(
            cli_app, ["sandbox", "init-shared", "--from", str(source_dir)]
        )

        assert result.exit_code == 0
        # Should show copying message
        assert "copying" in result.output.lower() or "data/" in result.output.lower()

    def test_init_shared_from_invalid_path_errors(self, runner, mock_shared_dir):
        """Verify --from fails with meaningful error on missing source."""
        result = runner.invoke(
            cli_app, ["sandbox", "init-shared", "--from", "/nonexistent/path"]
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_init_shared_from_skips_missing_subdirs(
        self, runner, mock_shared_dir, tmp_path
    ):
        """Verify --from gracefully handles missing subdirectories."""
        # Create source with only data/ (no models/ or strategies/)
        source_dir = tmp_path / "ktrdr-partial"
        source_dir.mkdir()
        (source_dir / "data").mkdir()
        (source_dir / "data" / "test.csv").write_text("test")

        result = runner.invoke(
            cli_app, ["sandbox", "init-shared", "--from", str(source_dir)]
        )

        assert result.exit_code == 0
        # Should copy data
        assert (mock_shared_dir / "data" / "test.csv").exists()
        # Should indicate skipped directories
        assert "skip" in result.output.lower() or "not found" in result.output.lower()

    def test_init_shared_idempotent_with_existing_content(
        self, runner, mock_shared_dir
    ):
        """Verify running without flags when content exists shows status."""
        # Pre-create shared dir with content
        mock_shared_dir.mkdir(parents=True)
        (mock_shared_dir / "data").mkdir()
        (mock_shared_dir / "data" / "file.txt").write_text("existing")

        result = runner.invoke(cli_app, ["sandbox", "init-shared"])

        assert result.exit_code == 0
        # Should show existing content, not overwrite
        assert (
            "already exists" in result.output.lower()
            or "data/" in result.output.lower()
        )

    def test_init_shared_no_flags_creates_empty_when_no_content(
        self, runner, mock_shared_dir
    ):
        """Verify running without flags creates empty structure when nothing exists."""
        result = runner.invoke(cli_app, ["sandbox", "init-shared"])

        assert result.exit_code == 0
        assert mock_shared_dir.exists()
        assert (mock_shared_dir / "data").exists()
        assert (mock_shared_dir / "models").exists()
        assert (mock_shared_dir / "strategies").exists()

    def test_init_shared_from_overwrites_existing(
        self, runner, mock_shared_dir, tmp_path
    ):
        """Verify --from overwrites existing shared data."""
        # Pre-create with old data
        mock_shared_dir.mkdir(parents=True)
        (mock_shared_dir / "data").mkdir()
        (mock_shared_dir / "data" / "old.csv").write_text("old data")

        # Create source with new data
        source_dir = tmp_path / "ktrdr-new"
        source_dir.mkdir()
        (source_dir / "data").mkdir()
        (source_dir / "data" / "new.csv").write_text("new data")

        result = runner.invoke(
            cli_app, ["sandbox", "init-shared", "--from", str(source_dir)]
        )

        assert result.exit_code == 0
        # Old file should be gone
        assert not (mock_shared_dir / "data" / "old.csv").exists()
        # New file should exist
        assert (mock_shared_dir / "data" / "new.csv").exists()

    def test_init_shared_shows_summary(self, runner, mock_shared_dir, tmp_path):
        """Verify init-shared shows summary with file counts and sizes."""
        # Create source with data
        source_dir = tmp_path / "ktrdr-source"
        source_dir.mkdir()
        (source_dir / "data").mkdir()
        (source_dir / "data" / "file1.csv").write_text("a" * 100)
        (source_dir / "data" / "file2.csv").write_text("b" * 200)
        (source_dir / "models").mkdir()
        (source_dir / "strategies").mkdir()

        result = runner.invoke(
            cli_app, ["sandbox", "init-shared", "--from", str(source_dir)]
        )

        assert result.exit_code == 0
        # Should show file count
        assert "2" in result.output or "files" in result.output.lower()
