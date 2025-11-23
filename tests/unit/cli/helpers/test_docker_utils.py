"""Tests for Docker utilities helper module."""

import re
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.helpers.docker_utils import DockerError, docker_login_ghcr


class TestDockerLoginGhcr:
    """Tests for docker_login_ghcr function."""

    def test_successful_login(self):
        """Test successful Docker login to GHCR."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Login Succeeded\n",
                returncode=0,
            )

            result = docker_login_ghcr(
                host="test.host.com",
                username="github_user",
                token="ghp_xxxxxxxxxxxx",
            )

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "ssh"
            assert call_args[1] == "test.host.com"
            assert "docker login" in call_args[2]
            # Check exact registry URL with word boundary (prevents partial matches)
            assert re.search(r"\bghcr\.io\b", call_args[2]) is not None

    def test_masks_token_in_dry_run(self, capsys):
        """Test that token is masked in dry-run output."""
        docker_login_ghcr(
            host="test.host.com",
            username="github_user",
            token="ghp_supersecrettoken123",
            dry_run=True,
        )

        captured = capsys.readouterr()
        # Token should be masked
        assert "ghp_supersecrettoken123" not in captured.out
        assert "***" in captured.out
        # Should show it's a dry run
        assert "DRY RUN" in captured.out

    def test_dry_run_returns_true(self):
        """Test dry-run mode returns True without executing."""
        with patch("subprocess.run") as mock_run:
            result = docker_login_ghcr(
                host="test.host.com",
                username="github_user",
                token="ghp_xxxx",
                dry_run=True,
            )

            assert result is True
            mock_run.assert_not_called()

    def test_handles_login_failure(self):
        """Test error handling when Docker login fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="unauthorized",
                returncode=1,
            )

            with pytest.raises(DockerError) as exc_info:
                docker_login_ghcr(
                    host="test.host.com",
                    username="github_user",
                    token="invalid_token",
                )

            assert "Docker login failed" in str(exc_info.value)

    def test_handles_ssh_failure(self):
        """Test error handling when SSH connection fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                255, "ssh", stderr="Connection refused"
            )

            with pytest.raises(DockerError) as exc_info:
                docker_login_ghcr(
                    host="test.host.com",
                    username="github_user",
                    token="ghp_xxxx",
                )

            assert "failed" in str(exc_info.value).lower()

    def test_handles_timeout(self):
        """Test error handling when command times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ssh", 30)

            with pytest.raises(DockerError) as exc_info:
                docker_login_ghcr(
                    host="test.host.com",
                    username="github_user",
                    token="ghp_xxxx",
                )

            assert "timed out" in str(exc_info.value).lower()

    def test_uses_correct_registry(self):
        """Test that login uses ghcr.io registry."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            docker_login_ghcr(
                host="test.host.com",
                username="github_user",
                token="ghp_xxxx",
            )

            call_args = mock_run.call_args[0][0]
            # Check exact registry URL with word boundary (prevents partial matches)
            assert re.search(r"\bghcr\.io\b", call_args[2]) is not None
