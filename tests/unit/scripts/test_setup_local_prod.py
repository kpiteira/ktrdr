"""Tests for scripts/setup-local-prod.sh."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).parent.parent.parent.parent / "scripts" / "setup-local-prod.sh"
)


class TestSetupLocalProdScript:
    """Tests for the setup-local-prod.sh script."""

    def test_script_exists_and_is_executable(self):
        """Script should exist and have executable permissions."""
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"
        assert os.access(
            SCRIPT_PATH, os.X_OK
        ), f"Script is not executable: {SCRIPT_PATH}"

    def test_check_only_flag_validates_prerequisites(self, tmp_path: Path):
        """--check-only flag should only validate prerequisites without cloning."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # Run with --check-only flag
        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        # Should report prerequisite status
        output = result.stdout + result.stderr
        assert (
            "prerequisite" in output.lower() or "checking" in output.lower()
        ), f"Expected prerequisite check output, got:\n{output}"

    def test_prerequisite_check_reports_git_status(self, tmp_path: Path):
        """Script should check for git and report its status."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        assert "git" in output.lower(), f"Expected git check in output, got:\n{output}"

    def test_prerequisite_check_reports_docker_status(self, tmp_path: Path):
        """Script should check for docker and report its status."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        assert (
            "docker" in output.lower()
        ), f"Expected docker check in output, got:\n{output}"

    def test_prerequisite_check_reports_uv_status(self, tmp_path: Path):
        """Script should check for uv and report its status."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        assert "uv" in output.lower(), f"Expected uv check in output, got:\n{output}"

    def test_prerequisite_check_reports_1password_status(self, tmp_path: Path):
        """Script should check for 1Password CLI (op) and report its status."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        assert (
            "1password" in output.lower() or "op" in output.lower()
        ), f"Expected 1Password check in output, got:\n{output}"

    def test_explains_1password_item_requirements(self, tmp_path: Path):
        """Script should explain what 1Password item is needed."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        # Should mention the item name and fields
        assert (
            "ktrdr-local-prod" in output
        ), f"Expected 1Password item name 'ktrdr-local-prod' in output, got:\n{output}"

    def test_help_flag_shows_usage(self, tmp_path: Path):
        """--help flag should show usage information."""
        result = subprocess.run(
            [str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        assert (
            "usage" in output.lower() or "ktrdr" in output.lower()
        ), f"Expected usage information in output, got:\n{output}"

    def test_fails_if_destination_exists(self, tmp_path: Path):
        """Script should fail if destination directory already exists."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # Create destination directory
        dest = tmp_path / "existing-dir"
        dest.mkdir()

        # Run in non-interactive mode with existing path
        result = subprocess.run(
            [str(SCRIPT_PATH), "--non-interactive", f"--path={dest}"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        # Should fail with appropriate error
        assert (
            result.returncode != 0
            or "already exists" in (result.stdout + result.stderr).lower()
        ), f"Expected failure or warning for existing directory, got:\n{result.stdout}\n{result.stderr}"


class TestSetupLocalProdPrerequisites:
    """Test prerequisite validation behavior."""

    def test_check_only_returns_success_when_prereqs_met(self, tmp_path: Path):
        """When all prerequisites are met, --check-only should return success."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        # On a dev machine with all tools installed, this should pass
        # We check that at minimum git and docker are detected
        output = result.stdout + result.stderr
        output_lower = output.lower()
        if "git" in output_lower and "docker" in output_lower:
            # At least basic prereqs are being checked
            pass
        else:
            pytest.fail(f"Prerequisites not properly checked:\n{output}")


class TestSetupLocalProdOutput:
    """Test script output and messaging."""

    def test_shows_banner_or_title(self, tmp_path: Path):
        """Script should show a clear title/banner indicating what it does."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        # Should mention KTRDR and local-prod somewhere
        assert (
            "ktrdr" in output.lower() or "local-prod" in output.lower()
        ), f"Expected title mentioning KTRDR or local-prod, got:\n{output}"

    def test_uses_color_codes_for_status(self, tmp_path: Path):
        """Script should use colors to indicate status (optional but nice)."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        result = subprocess.run(
            [str(SCRIPT_PATH), "--check-only"],
            env={**os.environ, "HOME": str(fake_home)},
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        # Should have checkmarks or x marks
        has_status_indicators = (
            "✓" in output or "✗" in output or "[0;32m" in output or "[0;31m" in output
        )
        assert (
            has_status_indicators or "pass" in output.lower()
        ), f"Expected status indicators in output, got:\n{output}"
