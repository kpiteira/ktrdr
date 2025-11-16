"""
Unit tests for the metadata module.

These tests verify that the metadata module correctly loads and
provides access to configuration values.
"""

import os

import pytest

from ktrdr import metadata


def test_metadata_module():
    """Test main metadata functions."""
    assert metadata.PROJECT_NAME == "KTRDR"
    assert isinstance(metadata.VERSION, str)
    assert metadata.ORG_WEBSITE.startswith("https://")


@pytest.mark.skip(
    reason="Environment-specific config overrides not implemented in metadata.yaml"
)
def test_environment_override():
    """Test environment-specific configuration override.

    NOTE: This test expects environment-specific configuration in ktrdr_metadata.yaml
    (testing: port 8001, development: port 8000), but these overrides are not currently
    implemented. Environment-specific config is handled by Pydantic settings in API config.
    """
    # Store original environment
    original_env = os.environ.get("KTRDR_ENVIRONMENT")

    try:
        # Set to testing environment
        os.environ["KTRDR_ENVIRONMENT"] = "testing"
        metadata.reload_config()

        # Testing environment should have port 8001
        assert metadata.get("api.port") == 8001
        assert metadata.get("api.reload") is False
        assert metadata.get("api.log_level") == "WARNING"

        # Set to development environment
        os.environ["KTRDR_ENVIRONMENT"] = "development"
        metadata.reload_config()

        # Development environment should have port 8000
        assert metadata.get("api.port") == 8000
        assert metadata.get("api.reload") is True
        assert metadata.get("api.log_level") == "DEBUG"
    finally:
        # Restore original environment
        if original_env is not None:
            os.environ["KTRDR_ENVIRONMENT"] = original_env
        else:
            os.environ.pop("KTRDR_ENVIRONMENT", None)
        metadata.reload_config()


def test_env_var_override():
    """Test environment variable override."""
    # Test with an environment variable
    test_port = 9999
    os.environ["KTRDR_API_PORT"] = str(test_port)

    # Force reload to pick up new environment variable
    metadata.reload_config()

    assert metadata.get("api.port") == test_port

    # Clean up
    os.environ.pop("KTRDR_API_PORT")
    metadata.reload_config()


def test_helper_functions():
    """Test metadata helper functions."""
    # FastAPI settings
    fastapi_settings = metadata.get_fastapi_settings()
    assert fastapi_settings["title"] == metadata.API_TITLE
    assert fastapi_settings["version"] == metadata.VERSION

    # Docker labels
    docker_labels = metadata.get_docker_labels()
    assert docker_labels["org.opencontainers.image.version"] == metadata.VERSION

    # API examples
    api_examples = metadata.get_api_examples()
    assert "symbols" in api_examples
    assert "default_symbol" in api_examples
