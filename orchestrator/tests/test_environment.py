"""Tests for orchestrator environment validation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.environment import validate_environment
from orchestrator.errors import OrchestratorError


class TestValidateEnvironment:
    """Tests for validate_environment() function."""

    def test_returns_cwd_when_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns current working directory when all checks pass."""
        # Setup: create .git directory and .env.sandbox file
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        # Mock subprocess.run to simulate sandbox running
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Status: running\n"

        with patch("subprocess.run", return_value=mock_result):
            result = validate_environment()

        assert result == tmp_path
        assert isinstance(result, Path)

    def test_raises_when_not_repo_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises OrchestratorError with 'repo root' message when .git missing."""
        # Setup: no .git directory
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        with pytest.raises(OrchestratorError) as exc_info:
            validate_environment()

        # Error should mention repo root and provide actionable guidance
        error_msg = str(exc_info.value).lower()
        assert "repo" in error_msg or "repository" in error_msg
        assert "root" in error_msg or "cd" in error_msg

    def test_raises_when_sandbox_not_initialized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises OrchestratorError with 'sandbox init' message when .env.sandbox missing."""
        # Setup: .git exists but no .env.sandbox
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        with pytest.raises(OrchestratorError) as exc_info:
            validate_environment()

        # Error should mention sandbox init command
        error_msg = str(exc_info.value).lower()
        assert "sandbox" in error_msg
        assert "init" in error_msg

    def test_raises_when_sandbox_not_running(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises OrchestratorError with 'sandbox up' message when status check fails."""
        # Setup: .git and .env.sandbox exist
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        # Mock subprocess.run to simulate sandbox not running
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Status: stopped\n"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(OrchestratorError) as exc_info:
                validate_environment()

        # Error should mention sandbox up command
        error_msg = str(exc_info.value).lower()
        assert "sandbox" in error_msg
        assert "up" in error_msg

    def test_raises_when_sandbox_status_command_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises OrchestratorError when sandbox status subprocess fails."""
        # Setup: .git and .env.sandbox exist
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        # Mock subprocess.run to simulate command failure
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: sandbox not found"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(OrchestratorError) as exc_info:
                validate_environment()

        # Error should mention sandbox up command
        error_msg = str(exc_info.value).lower()
        assert "sandbox" in error_msg
        assert "up" in error_msg

    def test_uses_uv_run_for_sandbox_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify subprocess is called with 'uv run ktrdr sandbox status'."""
        # Setup: all prerequisites present
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Status: running\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            validate_environment()

        # Verify the command used
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "uv" in cmd
        assert "ktrdr" in cmd
        assert "sandbox" in cmd
        assert "status" in cmd
