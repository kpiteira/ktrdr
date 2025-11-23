"""Tests for 1Password secrets helper module."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.helpers.secrets import (
    OnePasswordError,
    check_1password_authenticated,
    fetch_secrets_from_1password,
)


class TestFetchSecretsFrom1Password:
    """Tests for fetch_secrets_from_1password function."""

    def test_fetch_secrets_success(self):
        """Test successful secret fetching from 1Password."""
        mock_item = {
            "fields": [
                {"label": "username", "type": "STRING", "value": "user"},
                {"label": "db_password", "type": "CONCEALED", "value": "secret123"},
                {
                    "label": "jwt_secret",
                    "type": "CONCEALED",
                    "value": "jwt-secret-value",
                },
                {"label": "notes", "type": "STRING", "value": "some notes"},
            ]
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(mock_item),
                returncode=0,
            )

            secrets = fetch_secrets_from_1password("test-item")

            # Should only return CONCEALED fields
            assert secrets == {
                "db_password": "secret123",
                "jwt_secret": "jwt-secret-value",
            }

            # Verify correct command called
            mock_run.assert_called_once_with(
                ["op", "item", "get", "test-item", "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_fetch_secrets_not_signed_in(self):
        """Test error when not signed in to 1Password."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "op", stderr="not signed in"
            )

            with pytest.raises(OnePasswordError) as exc_info:
                fetch_secrets_from_1password("test-item")

            assert "Not signed in to 1Password" in str(exc_info.value)
            assert "op signin" in str(exc_info.value)

    def test_fetch_secrets_item_not_found(self):
        """Test error when item not found in 1Password."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "op", stderr="not found"
            )

            with pytest.raises(OnePasswordError) as exc_info:
                fetch_secrets_from_1password("missing-item")

            assert "not found" in str(exc_info.value).lower()
            assert "missing-item" in str(exc_info.value)

    def test_fetch_secrets_generic_error(self):
        """Test generic 1Password error handling."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "op", stderr="some other error"
            )

            with pytest.raises(OnePasswordError) as exc_info:
                fetch_secrets_from_1password("test-item")

            assert "1Password error" in str(exc_info.value)
            assert "some other error" in str(exc_info.value)

    def test_fetch_secrets_op_not_installed(self):
        """Test error when op CLI is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(OnePasswordError) as exc_info:
                fetch_secrets_from_1password("test-item")

            assert "not installed" in str(exc_info.value).lower()

    def test_fetch_secrets_empty_fields(self):
        """Test handling item with no CONCEALED fields."""
        mock_item = {
            "fields": [
                {"label": "username", "type": "STRING", "value": "user"},
            ]
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(mock_item),
                returncode=0,
            )

            secrets = fetch_secrets_from_1password("test-item")
            assert secrets == {}

    def test_fetch_secrets_missing_fields_key(self):
        """Test handling item with missing fields key."""
        mock_item = {}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(mock_item),
                returncode=0,
            )

            secrets = fetch_secrets_from_1password("test-item")
            assert secrets == {}


class TestCheck1PasswordAuthenticated:
    """Tests for check_1password_authenticated function."""

    def test_authenticated(self):
        """Test when 1Password CLI is authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            assert check_1password_authenticated() is True

            mock_run.assert_called_once_with(
                ["op", "account", "list"],
                capture_output=True,
                timeout=5,
            )

    def test_not_authenticated(self):
        """Test when 1Password CLI is not authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            assert check_1password_authenticated() is False

    def test_timeout(self):
        """Test timeout handling."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("op", 5)

            assert check_1password_authenticated() is False

    def test_op_not_installed(self):
        """Test when op CLI is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            assert check_1password_authenticated() is False
