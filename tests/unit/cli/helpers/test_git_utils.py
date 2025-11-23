"""Tests for git utilities helper module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.helpers.git_utils import GitError, get_latest_sha_tag


class TestGetLatestShaTag:
    """Tests for get_latest_sha_tag function."""

    def test_returns_formatted_sha(self):
        """Test successful SHA retrieval with correct format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="a1b2c3d\n",
                returncode=0,
            )

            result = get_latest_sha_tag()

            assert result == "sha-a1b2c3d"
            mock_run.assert_called_once_with(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from SHA."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="  abc1234  \n",
                returncode=0,
            )

            result = get_latest_sha_tag()

            assert result == "sha-abc1234"

    def test_handles_non_git_directory(self):
        """Test error when not in a git repository."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git", stderr="fatal: not a git repository"
            )

            with pytest.raises(GitError) as exc_info:
                get_latest_sha_tag()

            assert "Git error" in str(exc_info.value)

    def test_handles_git_not_installed(self):
        """Test error when git is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(GitError) as exc_info:
                get_latest_sha_tag()

            assert "not installed" in str(exc_info.value).lower()

    def test_handles_empty_repository(self):
        """Test error when repository has no commits."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git", stderr="fatal: ambiguous argument 'HEAD'"
            )

            with pytest.raises(GitError) as exc_info:
                get_latest_sha_tag()

            assert "Git error" in str(exc_info.value)
