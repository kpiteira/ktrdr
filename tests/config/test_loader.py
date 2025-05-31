"""
Tests for the configuration loader module.

This module tests the functionality of ConfigLoader for loading and validating YAML configurations.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from ktrdr.config.loader import ConfigLoader
from ktrdr.errors import (
    ConfigurationError,
    ConfigurationFileError,
    InvalidConfigurationError,
)


class TestConfigLoader:
    """Tests for the ConfigLoader class."""

    def test_load_valid_yaml(self):
        """Test loading valid YAML content."""
        # Sample valid YAML content matching the required KtrdrConfig structure
        yaml_content = """
        data:
          directory: ./data
          default_format: csv
        logging:
          level: INFO
          console_output: true
        debug: false
        """

        # Create a temporary file with the YAML content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_content)
            tmp_path = tmp.name

        try:
            # Load the config
            config_loader = ConfigLoader()
            config = config_loader.load(tmp_path)

            # Verify the configuration is loaded correctly
            assert config is not None
            assert config.data is not None
            assert (
                "data" in config.data.directory
            )  # Path is converted to absolute by validator
            assert config.logging.level == "INFO"
        finally:
            os.unlink(tmp_path)

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML content raises appropriate error."""
        # Invalid YAML content - malformed YAML with indentation error
        yaml_content = """
        data:
          directory: ./data
        logging:
        level: INFO  # This is indented incorrectly - should be under logging
        """

        # Create a temporary file with invalid YAML content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_content)
            tmp_path = tmp.name

        try:
            # Should raise an error
            with pytest.raises(InvalidConfigurationError) as excinfo:
                config_loader = ConfigLoader()
                config_loader.load(tmp_path)

            # Either should fail due to YAML parsing or validation error
            assert (
                "validation failed" in str(excinfo.value).lower()
                or "yaml" in str(excinfo.value).lower()
            )
        finally:
            # Clean up the temporary file
            os.unlink(tmp_path)

    def test_load_file_not_found(self):
        """Test loading from a non-existent file raises appropriate error."""
        # Use a path that doesn't exist
        with pytest.raises(ConfigurationFileError) as excinfo:
            config_loader = ConfigLoader()
            config_loader.load("/path/to/nonexistent/file.yaml")

        assert "not found" in str(excinfo.value)
        assert "CONF-FileNotFound" in excinfo.value.error_code

    def test_load_from_env_with_valid_env(self):
        """Test loading config from environment variable."""
        # Create temporary file with test config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(
                """
            data:
              directory: ./data
              default_format: csv
            logging:
              level: DEBUG
            """
            )
            tmp_path = tmp.name

        try:
            # Set environment variable
            with patch.dict(os.environ, {"KTRDR_CONFIG": tmp_path}):
                config_loader = ConfigLoader()
                config = config_loader.load_from_env("KTRDR_CONFIG")

                # Verify the result
                assert config is not None
                assert config.data is not None
                assert (
                    "data" in config.data.directory
                )  # Path is converted to absolute by validator
                assert config.logging.level == "DEBUG"
        finally:
            # Clean up the temporary file
            os.unlink(tmp_path)

    def test_load_from_env_with_default(self):
        """Test loading config with default path when env variable is not set."""
        # Create temporary file with valid config matching the KtrdrConfig structure
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(
                """
            data:
              directory: ./data
              default_format: parquet
            logging:
              level: WARNING
            """
            )
            tmp_path = tmp.name

        try:
            # Ensure environment variable is not set
            with patch.dict(os.environ, {}, clear=True):
                config_loader = ConfigLoader()
                config = config_loader.load_from_env(
                    "KTRDR_CONFIG", default_path=tmp_path
                )

                # Verify result matches our test config
                assert config is not None
                assert (
                    "data" in config.data.directory
                )  # Path is converted to absolute by validator
                assert config.data.default_format == "parquet"
                assert config.logging.level == "WARNING"
        finally:
            # Clean up the temporary file
            os.unlink(tmp_path)

    def test_load_from_env_missing(self):
        """Test handling of missing environment variable and no default path."""
        # Ensure environment variable is not set
        with patch.dict(os.environ, {}, clear=True):
            config_loader = ConfigLoader()
            # The current implementation uses a fallback strategy that returns None
            # rather than raising an exception
            result = config_loader.load_from_env("KTRDR_CONFIG")
            assert result is None
