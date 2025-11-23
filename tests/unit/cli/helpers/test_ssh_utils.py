"""Tests for SSH utilities helper module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.helpers.ssh_utils import SSHError, ssh_exec_with_env


class TestSshExecWithEnv:
    """Tests for ssh_exec_with_env function."""

    def test_successful_execution(self):
        """Test successful SSH command execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="command output\n",
                returncode=0,
            )

            result = ssh_exec_with_env(
                host="test.host.com",
                workdir="/opt/app",
                env_vars={"FOO": "bar"},
                command="docker compose up -d",
            )

            assert result == "command output\n"
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            ssh_cmd = call_args[0][0]
            assert ssh_cmd[0] == "ssh"
            assert ssh_cmd[1] == "test.host.com"
            assert "FOO=bar" in ssh_cmd[2]  # shlex.quote doesn't quote simple values
            assert "docker compose up -d" in ssh_cmd[2]
            assert "cd /opt/app" in ssh_cmd[2]

    def test_quotes_special_characters(self):
        """Test that special characters in env vars are properly quoted."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)

            ssh_exec_with_env(
                host="test.host.com",
                workdir="/opt/app",
                env_vars={"PASSWORD": "p@ss'word$123"},
                command="echo test",
            )

            call_args = mock_run.call_args[0][0]
            # shlex.quote should properly escape the value
            assert "PASSWORD=" in call_args[2]

    def test_dry_run_returns_none(self):
        """Test dry-run mode returns None without executing."""
        with patch("subprocess.run") as mock_run:
            result = ssh_exec_with_env(
                host="test.host.com",
                workdir="/opt/app",
                env_vars={"FOO": "bar"},
                command="docker compose up -d",
                dry_run=True,
            )

            assert result is None
            mock_run.assert_not_called()

    def test_dry_run_masks_passwords(self, capsys):
        """Test that dry-run masks password-like values."""
        ssh_exec_with_env(
            host="test.host.com",
            workdir="/opt/app",
            env_vars={
                "DB_PASSWORD": "supersecret123",
                "JWT_SECRET": "mysecrettoken",
                "GHCR_TOKEN": "ghp_xxxx",
                "NORMAL_VAR": "visible",
            },
            command="docker compose up -d",
            dry_run=True,
        )

        captured = capsys.readouterr()
        # Secrets should be masked
        assert "supersecret123" not in captured.out
        assert "mysecrettoken" not in captured.out
        assert "ghp_xxxx" not in captured.out
        # Non-secrets should be visible
        assert "visible" in captured.out
        # Should show it's a dry run
        assert "DRY RUN" in captured.out

    def test_handles_ssh_failure(self):
        """Test error handling when SSH command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "ssh", stderr="Connection refused"
            )

            with pytest.raises(SSHError) as exc_info:
                ssh_exec_with_env(
                    host="test.host.com",
                    workdir="/opt/app",
                    env_vars={},
                    command="echo test",
                )

            assert "SSH command failed" in str(exc_info.value)
            assert "Connection refused" in str(exc_info.value)

    def test_handles_timeout(self):
        """Test error handling when SSH command times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ssh", 300)

            with pytest.raises(SSHError) as exc_info:
                ssh_exec_with_env(
                    host="test.host.com",
                    workdir="/opt/app",
                    env_vars={},
                    command="long-running-command",
                )

            assert "timed out" in str(exc_info.value).lower()

    def test_multiple_env_vars(self):
        """Test with multiple environment variables."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)

            ssh_exec_with_env(
                host="test.host.com",
                workdir="/opt/app",
                env_vars={
                    "VAR1": "value1",
                    "VAR2": "value2",
                    "VAR3": "value3",
                },
                command="echo test",
            )

            call_args = mock_run.call_args[0][0]
            assert "VAR1=" in call_args[2]
            assert "VAR2=" in call_args[2]
            assert "VAR3=" in call_args[2]

    def test_empty_env_vars(self):
        """Test with empty environment variables dict."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="ok", returncode=0)

            ssh_exec_with_env(
                host="test.host.com",
                workdir="/opt/app",
                env_vars={},
                command="echo test",
            )

            call_args = mock_run.call_args[0][0]
            assert "cd /opt/app &&  echo test" in call_args[2]
