"""
Unit tests for deployment configuration files.

Tests validate configuration file structure and content
for different environments (dev, prod).
"""

from pathlib import Path

import yaml


# Configuration file paths
WORKERS_DEV_CONFIG = Path("config/workers.dev.yaml")
WORKERS_PROD_CONFIG = Path("config/workers.prod.yaml")
DEV_ENV_TEMPLATE = Path("config/deploy/dev.env.example")
PROD_ENV_TEMPLATE = Path("config/deploy/prod.env.example")


class TestConfigurationFilesExist:
    """Test that configuration files exist."""

    def test_workers_dev_config_exists(self):
        """Development workers config should exist."""
        assert WORKERS_DEV_CONFIG.exists(), f"Config not found at {WORKERS_DEV_CONFIG}"

    def test_workers_prod_config_exists(self):
        """Production workers config should exist."""
        assert (
            WORKERS_PROD_CONFIG.exists()
        ), f"Config not found at {WORKERS_PROD_CONFIG}"

    def test_dev_env_template_exists(self):
        """Development .env template should exist."""
        assert DEV_ENV_TEMPLATE.exists(), f"Template not found at {DEV_ENV_TEMPLATE}"

    def test_prod_env_template_exists(self):
        """Production .env template should exist."""
        assert (
            PROD_ENV_TEMPLATE.exists()
        ), f"Template not found at {PROD_ENV_TEMPLATE}"


class TestWorkersDevConfig:
    """Test development workers configuration."""

    def test_is_valid_yaml(self):
        """Config file should be valid YAML."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        assert data is not None, "Config file is empty"

    def test_has_workers_section(self):
        """Config should have workers section."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "workers" in data, "Config must have 'workers' section"

    def test_has_backend_api_url(self):
        """Config should specify backend API URL."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "backend_api_url" in data, "Config must specify backend_api_url"

    def test_backend_api_url_is_valid(self):
        """Backend API URL should be valid HTTP URL."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        url = data.get("backend_api_url", "")
        assert url.startswith("http"), "backend_api_url must be HTTP URL"

    def test_workers_is_list(self):
        """Workers section should be a list."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        assert isinstance(data["workers"], list), "workers must be a list"

    def test_workers_have_required_fields(self):
        """Each worker should have required fields."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        for worker in data["workers"]:
            assert "id" in worker, "Worker must have 'id'"
            assert "ip" in worker, "Worker must have 'ip'"
            assert "type" in worker, "Worker must have 'type'"

    def test_worker_types_are_valid(self):
        """Worker types should be backtesting or training."""
        with open(WORKERS_DEV_CONFIG) as f:
            data = yaml.safe_load(f)
        for worker in data["workers"]:
            assert worker["type"] in [
                "backtesting",
                "training",
            ], "Worker type must be 'backtesting' or 'training'"


class TestWorkersProdConfig:
    """Test production workers configuration."""

    def test_is_valid_yaml(self):
        """Config file should be valid YAML."""
        with open(WORKERS_PROD_CONFIG) as f:
            data = yaml.safe_load(f)
        assert data is not None, "Config file is empty"

    def test_has_workers_section(self):
        """Config should have workers section."""
        with open(WORKERS_PROD_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "workers" in data, "Config must have 'workers' section"

    def test_has_backend_api_url(self):
        """Config should specify backend API URL."""
        with open(WORKERS_PROD_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "backend_api_url" in data, "Config must specify backend_api_url"

    def test_workers_is_list(self):
        """Workers section should be a list."""
        with open(WORKERS_PROD_CONFIG) as f:
            data = yaml.safe_load(f)
        assert isinstance(data["workers"], list), "workers must be a list"

    def test_workers_have_required_fields(self):
        """Each worker should have required fields."""
        with open(WORKERS_PROD_CONFIG) as f:
            data = yaml.safe_load(f)
        for worker in data["workers"]:
            assert "id" in worker, "Worker must have 'id'"
            assert "ip" in worker, "Worker must have 'ip'"
            assert "type" in worker, "Worker must have 'type'"


class TestDevEnvTemplate:
    """Test development .env template."""

    def test_has_backend_api_url(self):
        """Template should have KTRDR_BACKEND_API variable."""
        with open(DEV_ENV_TEMPLATE) as f:
            content = f.read()
        assert (
            "KTRDR_BACKEND_API" in content
        ), "Template must define KTRDR_BACKEND_API"

    def test_has_gateway(self):
        """Template should have KTRDR_GATEWAY variable."""
        with open(DEV_ENV_TEMPLATE) as f:
            content = f.read()
        assert "KTRDR_GATEWAY" in content, "Template must define KTRDR_GATEWAY"

    def test_has_netmask(self):
        """Template should have KTRDR_NETMASK variable."""
        with open(DEV_ENV_TEMPLATE) as f:
            content = f.read()
        assert "KTRDR_NETMASK" in content, "Template must define KTRDR_NETMASK"

    def test_has_git_repo(self):
        """Template should have KTRDR_GIT_REPO variable."""
        with open(DEV_ENV_TEMPLATE) as f:
            content = f.read()
        assert "KTRDR_GIT_REPO" in content, "Template must define KTRDR_GIT_REPO"


class TestProdEnvTemplate:
    """Test production .env template."""

    def test_has_backend_api_url(self):
        """Template should have KTRDR_BACKEND_API variable."""
        with open(PROD_ENV_TEMPLATE) as f:
            content = f.read()
        assert (
            "KTRDR_BACKEND_API" in content
        ), "Template must define KTRDR_BACKEND_API"

    def test_has_gateway(self):
        """Template should have KTRDR_GATEWAY variable."""
        with open(PROD_ENV_TEMPLATE) as f:
            content = f.read()
        assert "KTRDR_GATEWAY" in content, "Template must define KTRDR_GATEWAY"

    def test_has_netmask(self):
        """Template should have KTRDR_NETMASK variable."""
        with open(PROD_ENV_TEMPLATE) as f:
            content = f.read()
        assert "KTRDR_NETMASK" in content, "Template must define KTRDR_NETMASK"

    def test_has_git_repo(self):
        """Template should have KTRDR_GIT_REPO variable."""
        with open(PROD_ENV_TEMPLATE) as f:
            content = f.read()
        assert "KTRDR_GIT_REPO" in content, "Template must define KTRDR_GIT_REPO"


class TestConfigurationConsistency:
    """Test consistency between dev and prod configs."""

    def test_same_required_fields(self):
        """Dev and prod configs should have same structure."""
        with open(WORKERS_DEV_CONFIG) as f:
            dev_data = yaml.safe_load(f)
        with open(WORKERS_PROD_CONFIG) as f:
            prod_data = yaml.safe_load(f)

        # Both should have same top-level keys
        dev_keys = set(dev_data.keys())
        prod_keys = set(prod_data.keys())
        assert (
            dev_keys == prod_keys
        ), "Dev and prod configs should have same structure"
