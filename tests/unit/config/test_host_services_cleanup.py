"""
Tests for Task 5.3: Environment Variable Cleanup

Verifies that the system works correctly after removing deprecated
environment variables for distributed-only mode.

Tests cover:
- IB Host Service settings still work (should be kept)
- Training Host Service settings are removed
- No TrainingHostServiceSettings class exists
- Workers don't set deprecated environment variables
"""

import os
from unittest.mock import patch

import pytest


class TestIBHostServiceStillWorks:
    """IB Host Service should still function (not removed)."""

    def test_ib_host_service_settings_exists(self):
        """IB Host Service settings should still exist."""
        from ktrdr.config.host_services import IbHostServiceSettings

        settings = IbHostServiceSettings()
        assert settings is not None

    def test_ib_host_service_can_be_enabled(self):
        """IB Host Service can be enabled via environment variable."""
        with patch.dict(os.environ, {"USE_IB_HOST_SERVICE": "true"}):
            from ktrdr.config.host_services import IbHostServiceSettings

            settings = IbHostServiceSettings()
            assert settings.enabled is True

    def test_ib_host_service_url_configurable(self):
        """IB Host Service URL can be configured."""
        with patch.dict(os.environ, {"IB_HOST_SERVICE_URL": "http://custom:5001"}):
            from ktrdr.config.host_services import IbHostServiceSettings

            settings = IbHostServiceSettings()
            assert settings.base_url == "http://custom:5001"


class TestTrainingHostServiceRemoved:
    """Training Host Service settings should be removed."""

    def test_training_host_service_settings_does_not_exist(self):
        """TrainingHostServiceSettings class should not exist."""
        with pytest.raises(ImportError):
            pass  # noqa: F401, I001

    def test_get_training_host_service_settings_does_not_exist(self):
        """get_training_host_service_settings function should not exist."""
        from ktrdr.config import host_services

        assert not hasattr(host_services, "get_training_host_service_settings")

    def test_get_training_host_url_does_not_exist(self):
        """get_training_host_url function should not exist."""
        from ktrdr.config import host_services

        assert not hasattr(host_services, "get_training_host_url")


class TestDeprecatedEnvVarsNotUsed:
    """Deprecated environment variables should not be used anywhere."""

    def test_use_remote_backtest_service_not_in_worker(self):
        """Backtest worker should not set USE_REMOTE_BACKTEST_SERVICE."""
        # Read the backtest_worker.py file
        with open("ktrdr/backtesting/backtest_worker.py") as f:
            content = f.read()

        # Should not contain USE_REMOTE_BACKTEST_SERVICE
        assert "USE_REMOTE_BACKTEST_SERVICE" not in content

    def test_use_training_host_service_not_in_worker(self):
        """Training worker should not set USE_TRAINING_HOST_SERVICE."""
        # Read the training_worker_api.py file
        with open("ktrdr/training/training_worker_api.py") as f:
            content = f.read()

        # Should not contain USE_TRAINING_HOST_SERVICE
        assert "USE_TRAINING_HOST_SERVICE" not in content


class TestDockerComposeClean:
    """Docker compose should not reference deprecated variables."""

    def test_docker_compose_no_training_host_vars(self):
        """docker-compose.yml should not reference USE_TRAINING_HOST_SERVICE."""
        with open("docker/docker-compose.yml") as f:
            content = f.read()

        assert "USE_TRAINING_HOST_SERVICE" not in content
        assert "TRAINING_HOST_SERVICE_URL" not in content

    def test_docker_compose_no_remote_backtest_vars(self):
        """docker-compose.yml should not reference USE_REMOTE_BACKTEST_SERVICE."""
        with open("docker/docker-compose.yml") as f:
            content = f.read()

        assert "USE_REMOTE_BACKTEST_SERVICE" not in content
        assert "REMOTE_BACKTEST_SERVICE_URL" not in content

    def test_docker_compose_still_has_ib_vars(self):
        """docker-compose.yml should still have IB host service variables."""
        with open("docker/docker-compose.yml") as f:
            content = f.read()

        # IB variables should still exist
        assert "USE_IB_HOST_SERVICE" in content
        assert "IB_HOST_SERVICE_URL" in content


class TestSystemStartsWithoutDeprecatedVars:
    """System should start successfully without deprecated variables."""

    def test_backend_starts_without_training_host_vars(self):
        """Backend can initialize without USE_TRAINING_HOST_SERVICE."""
        # Remove the env var if it exists
        with patch.dict(os.environ, {}, clear=False):
            if "USE_TRAINING_HOST_SERVICE" in os.environ:
                del os.environ["USE_TRAINING_HOST_SERVICE"]
            if "TRAINING_HOST_SERVICE_URL" in os.environ:
                del os.environ["TRAINING_HOST_SERVICE_URL"]

            # This should not raise an error
            from ktrdr.config import host_services

            # Should still be able to get IB settings
            ib_settings = host_services.get_ib_host_service_settings()
            assert ib_settings is not None

    def test_workers_start_without_remote_backtest_vars(self):
        """Workers can start without USE_REMOTE_BACKTEST_SERVICE."""
        with patch.dict(os.environ, {}, clear=False):
            if "USE_REMOTE_BACKTEST_SERVICE" in os.environ:
                del os.environ["USE_REMOTE_BACKTEST_SERVICE"]
            if "REMOTE_BACKTEST_SERVICE_URL" in os.environ:
                del os.environ["REMOTE_BACKTEST_SERVICE_URL"]

            # This should not raise an error when importing worker modules
            # (we're not actually starting the workers, just verifying imports work)
            try:
                import ktrdr.backtesting.backtest_worker  # noqa: F401

                success = True
            except Exception:
                success = False

            assert (
                success
            ), "Backtest worker should import without USE_REMOTE_BACKTEST_SERVICE"
