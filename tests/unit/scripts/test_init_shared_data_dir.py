"""Tests for scripts/init-shared-data-dir.sh."""

import os
import subprocess
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).parent.parent.parent.parent / "scripts" / "init-shared-data-dir.sh"
)


class TestInitSharedDataDir:
    """Tests for the init-shared-data-dir.sh script."""

    def test_script_exists_and_is_executable(self):
        """Script should exist and have executable permissions."""
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"
        assert os.access(
            SCRIPT_PATH, os.X_OK
        ), f"Script is not executable: {SCRIPT_PATH}"

    def test_creates_shared_directories(self, tmp_path: Path):
        """Script should create data, models, and strategies subdirectories."""
        # Set up a temporary HOME
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # Run the script with modified HOME
        result = subprocess.run(
            [str(SCRIPT_PATH)],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Verify directories were created
        shared_dir = fake_home / ".ktrdr" / "shared"
        assert (shared_dir / "data").is_dir(), "data directory not created"
        assert (shared_dir / "models").is_dir(), "models directory not created"
        assert (shared_dir / "strategies").is_dir(), "strategies directory not created"

    def test_is_idempotent(self, tmp_path: Path):
        """Script should be safe to run multiple times."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # Run twice
        for _ in range(2):
            result = subprocess.run(
                [str(SCRIPT_PATH)],
                env={**os.environ, "HOME": str(fake_home)},
                capture_output=True,
                text=True,
            )
            assert (
                result.returncode == 0
            ), f"Script failed on repeated run: {result.stderr}"

        # Directories should still exist
        shared_dir = fake_home / ".ktrdr" / "shared"
        assert (shared_dir / "data").is_dir()
        assert (shared_dir / "models").is_dir()
        assert (shared_dir / "strategies").is_dir()

    def test_prints_helpful_output(self, tmp_path: Path):
        """Script should print informative output."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH)],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Check for key information in output
        assert "shared" in result.stdout.lower() or ".ktrdr" in result.stdout
        assert "data" in result.stdout
        assert "models" in result.stdout
        assert "strategies" in result.stdout
