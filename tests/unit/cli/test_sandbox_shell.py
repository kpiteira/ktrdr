"""Unit tests for sandbox shell command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSandboxShell:
    """Tests for ktrdr sandbox shell command."""

    @pytest.fixture
    def sandbox_env(self, tmp_path: Path) -> dict[str, str]:
        """Create a mock sandbox environment."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test-instance\nSLOT_NUMBER=1\n")
        return {"INSTANCE_ID": "test-instance", "SLOT_NUMBER": "1"}

    @pytest.fixture
    def compose_file(self, tmp_path: Path) -> Path:
        """Create a mock compose file."""
        compose = tmp_path / "docker-compose.sandbox.yml"
        compose.write_text("version: '3'\nservices:\n  backend:\n    image: test\n")
        return compose

    def test_shell_default_service(
        self, tmp_path: Path, sandbox_env: dict[str, str], compose_file: Path
    ) -> None:
        """Verify default argument is 'backend'."""
        from ktrdr.cli.sandbox import shell

        with (
            patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path),
            patch("ktrdr.cli.sandbox.load_env_sandbox", return_value=sandbox_env),
            patch("ktrdr.cli.sandbox.find_compose_file", return_value=compose_file),
            patch("ktrdr.cli.sandbox.subprocess.run") as mock_run,
        ):
            # First call for bash succeeds
            mock_run.return_value = MagicMock(returncode=0)

            # Call with explicit default to avoid Typer ArgumentInfo wrapper
            shell(service="backend")

            # Verify docker compose exec was called with 'backend' as default service
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert "docker" in cmd
            assert "compose" in cmd
            assert "exec" in cmd
            assert "backend" in cmd
            assert "bash" in cmd

    def test_shell_custom_service(
        self, tmp_path: Path, sandbox_env: dict[str, str], compose_file: Path
    ) -> None:
        """Verify custom service passed to docker command."""
        from ktrdr.cli.sandbox import shell

        with (
            patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path),
            patch("ktrdr.cli.sandbox.load_env_sandbox", return_value=sandbox_env),
            patch("ktrdr.cli.sandbox.find_compose_file", return_value=compose_file),
            patch("ktrdr.cli.sandbox.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)

            shell(service="db")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert "db" in cmd
            assert "backend" not in cmd

    def test_shell_not_in_sandbox_directory(self, tmp_path: Path) -> None:
        """Verify error when .env.sandbox missing."""
        import typer

        from ktrdr.cli.sandbox import shell

        # tmp_path has no .env.sandbox file
        with (
            patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path),
            patch("ktrdr.cli.sandbox.load_env_sandbox", return_value={}),
            pytest.raises(typer.Exit) as exc_info,
        ):
            shell(service="backend")

        assert exc_info.value.exit_code == 1

    def test_shell_no_compose_file(
        self, tmp_path: Path, sandbox_env: dict[str, str]
    ) -> None:
        """Verify error when compose file missing."""
        import typer

        from ktrdr.cli.sandbox import shell

        with (
            patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path),
            patch("ktrdr.cli.sandbox.load_env_sandbox", return_value=sandbox_env),
            patch(
                "ktrdr.cli.sandbox.find_compose_file",
                side_effect=FileNotFoundError("No docker-compose file found"),
            ),
            pytest.raises(typer.Exit) as exc_info,
        ):
            shell(service="backend")

        assert exc_info.value.exit_code == 1

    def test_shell_bash_fallback_to_sh(
        self, tmp_path: Path, sandbox_env: dict[str, str], compose_file: Path
    ) -> None:
        """Verify fallback to sh when bash unavailable (exit code 126)."""
        from ktrdr.cli.sandbox import shell

        with (
            patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path),
            patch("ktrdr.cli.sandbox.load_env_sandbox", return_value=sandbox_env),
            patch("ktrdr.cli.sandbox.find_compose_file", return_value=compose_file),
            patch("ktrdr.cli.sandbox.subprocess.run") as mock_run,
        ):
            # First call for bash fails with exit code 126 (command not found)
            # Second call for sh succeeds
            mock_run.side_effect = [
                MagicMock(returncode=126),
                MagicMock(returncode=0),
            ]

            shell(service="backend")

            assert mock_run.call_count == 2

            # First call tried bash
            first_call = mock_run.call_args_list[0]
            assert "bash" in first_call[0][0]

            # Second call tried sh
            second_call = mock_run.call_args_list[1]
            assert "sh" in second_call[0][0]
